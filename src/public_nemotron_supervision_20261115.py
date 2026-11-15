# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0
# Derived from official NeMo pure supervision code. Forward bodies unchanged.
# NeMo framework typing/decorators replaced by plain torch.nn.Module boundary.
from typing import Dict,List,Optional,Sequence,Tuple,Union
from numbers import Real
import logging,math
import numpy as np
import torch
import torch.nn.functional as F
from scipy.optimize import linear_sum_assignment

def find_first_nonzero(mat: torch.Tensor, max_cap_val=-1, thres: float=0.5) -> torch.Tensor:
    """
    Finds the first nonzero value in the matrix, discretizing it to the specified maximum capacity.

    Args:
        mat (Tensor): A torch tensor representing the matrix.
        max_cap_val (int): The maximum capacity to which the matrix values will be discretized.
        thres (float): The threshold value for discretizing the matrix values.

    Returns:
        mask_max_indices (Tensor): A torch tensor representing the discretized matrix with the first
        nonzero value in each row.
    """
    labels_discrete = mat.clone()
    labels_discrete[labels_discrete < thres] = 0
    labels_discrete[labels_discrete >= thres] = 1
    non_zero_mask = labels_discrete != 0
    mask_max_values, mask_max_indices = torch.max(non_zero_mask, dim=1)
    mask_max_indices[mask_max_values == 0] = max_cap_val
    return mask_max_indices

def _validate_hungarian_target_inputs(labels: torch.Tensor, preds: torch.Tensor, assignment_mask: Optional[torch.Tensor]=None) -> None:
    """
    Validate tensor shapes used by the Hungarian target generators.

    Args:
        labels (torch.Tensor): Ground-truth labels with shape ``(B, T, S)``.
        preds (torch.Tensor): Predicted speaker probabilities with shape ``(B, T, N)``.
        assignment_mask (Optional[torch.Tensor]): Feasible assignments with shape ``(B, S, N)``, or ``None`` to
            permit every label-to-stream pairing.
    """
    if labels.ndim != 3 or preds.ndim != 3:
        raise ValueError(f'labels and preds must be 3-D tensors with shapes (B, T, S) and (B, T, N), got {labels.shape} and {preds.shape}')
    if labels.shape[:2] != preds.shape[:2]:
        raise ValueError(f'labels and preds must have the same batch and time dimensions, got {labels.shape} and {preds.shape}')
    if labels.device != preds.device:
        raise ValueError(f'labels and preds must be on the same device, got {labels.device} and {preds.device}')
    if labels.shape[1] == 0 or labels.shape[2] == 0 or preds.shape[2] == 0:
        raise ValueError(f'labels and preds must have non-empty time and speaker dimensions, got {labels.shape}')
    if assignment_mask is not None and assignment_mask.shape != (labels.shape[0], labels.shape[2], preds.shape[2]):
        raise ValueError(f'assignment_mask must have shape {(labels.shape[0], labels.shape[2], preds.shape[2])}, got {assignment_mask.shape}')

def get_pil_targets_hungarian(labels: torch.Tensor, preds: torch.Tensor, assignment_mask: Optional[torch.Tensor]=None) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Generate permutation-invariant targets with the Hungarian assignment algorithm.

    The pair-wise score is the mean dot product over time. Unlike exhaustive permutation
    enumeration, this implementation scales polynomially with the speaker count and supports
    a different number of label speakers and prediction streams.

    Args:
        labels (torch.Tensor): Ground-truth labels with shape ``(B, T, S)``.
        preds (torch.Tensor): Predicted speaker probabilities with shape ``(B, T, N)``.
        assignment_mask (Optional[torch.Tensor]): Optional feasibility mask with shape ``(B, S, N)``. ``False`` entries
            are excluded from the assignment.

    Returns:
        aligned_labels (torch.Tensor): Labels aligned to prediction streams with shape ``(B, T, N)``.
        speaker_indices (torch.Tensor): Source label indices with shape ``(B, N)``. Unmatched streams and streams
            assigned to inactive speakers contain ``-1``.
    """
    _validate_hungarian_target_inputs(labels, preds, assignment_mask)
    batch_size, num_frames, num_label_speakers = labels.shape
    num_pred_speakers = preds.shape[2]
    if batch_size == 0:
        aligned_labels = labels.new_zeros((0, num_frames, num_pred_speakers))
        speaker_indices = torch.full((0, num_pred_speakers), -1, device=labels.device, dtype=torch.long)
        return (aligned_labels, speaker_indices)
    with torch.no_grad():
        with torch.autocast(device_type=preds.device.type, enabled=False):
            match_score = torch.einsum('bts,btn->bsn', labels.float(), preds.float()) / num_frames
        active_speakers = torch.any(labels > 0.5, dim=1)
        assignment_size = min(num_label_speakers, num_pred_speakers)
        score_min = match_score.amin(dim=(1, 2), keepdim=True)
        score_max = match_score.amax(dim=(1, 2), keepdim=True)
        inactive_score = score_min - (assignment_size + 1) * (score_max - score_min + 1.0)
        match_score = torch.where(active_speakers.unsqueeze(2), match_score, inactive_score)
        cost_matrix = -match_score
        if assignment_mask is not None:
            assignment_mask = assignment_mask.to(device=labels.device, dtype=torch.bool)
            cost_matrix = cost_matrix.masked_fill(~assignment_mask, float('inf'))
        cost_matrix_np = cost_matrix.to(device='cpu', dtype=torch.float32).numpy()
        if assignment_mask is None:
            finite_costs = cost_matrix_np
        else:
            finite_costs = cost_matrix_np[assignment_mask.cpu().numpy()]
        if not np.isfinite(finite_costs).all():
            raise ValueError('Hungarian assignment costs contain NaN or infinite values')
        batch_row_indices = []
        batch_col_indices = []
        for batch_idx in range(batch_size):
            try:
                row_indices, col_indices = linear_sum_assignment(cost_matrix_np[batch_idx])
            except ValueError as error:
                raise ValueError(f'No feasible speaker assignment for batch item {batch_idx}') from error
            batch_row_indices.append(torch.as_tensor(row_indices, device=labels.device))
            batch_col_indices.append(torch.as_tensor(col_indices, device=labels.device))
        batch_row_indices = torch.stack(batch_row_indices)
        batch_col_indices = torch.stack(batch_col_indices)
        permutation_matrix = labels.new_zeros((batch_size, num_label_speakers, num_pred_speakers))
        batch_indices = torch.arange(batch_size, device=labels.device).unsqueeze(1).expand_as(batch_row_indices)
        permutation_matrix[batch_indices, batch_row_indices, batch_col_indices] = 1
        aligned_labels = torch.matmul(labels, permutation_matrix).to(labels.dtype)
        speaker_indices = torch.full((batch_size, num_pred_speakers), -1, device=labels.device, dtype=torch.long)
        matched_speakers_are_active = active_speakers[batch_indices, batch_row_indices]
        speaker_indices[batch_indices, batch_col_indices] = torch.where(matched_speakers_are_active, batch_row_indices, torch.full_like(batch_row_indices, -1))
    return (aligned_labels, speaker_indices)

def get_ats_targets_hungarian(labels: torch.Tensor, preds: torch.Tensor, thres: float=0.5, tolerance: float=0) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Generate arrival-time-sorted targets with the Hungarian assignment algorithm.

    Speakers with arrival times within ``tolerance`` frames may exchange output positions;
    prediction overlap resolves those ties. Rectangular inputs use the earliest label speakers
    when there are fewer prediction streams and leave extra prediction streams unmatched.

    Args:
        labels (torch.Tensor): Ground-truth labels with shape ``(B, T, S)``.
        preds (torch.Tensor): Predicted speaker probabilities with shape ``(B, T, N)``.
        thres (float): Activity threshold used to determine each speaker's first active frame.
        tolerance (float): Maximum arrival-time difference, in frames, allowed for an assignment.

    Returns:
        aligned_labels (torch.Tensor): Labels aligned to arrival-time-compatible streams with shape ``(B, T, N)``.
        speaker_indices (torch.Tensor): Source label indices with shape ``(B, N)``; unmatched streams contain ``-1``.
    """
    _validate_hungarian_target_inputs(labels, preds)
    if tolerance < 0:
        raise ValueError(f'tolerance must be non-negative, got {tolerance}')
    num_label_speakers = labels.shape[2]
    num_pred_speakers = preds.shape[2]
    arrival = find_first_nonzero(labels, max_cap_val=labels.shape[1], thres=thres)
    sorted_arrival = torch.sort(arrival, dim=1).values
    if num_label_speakers <= num_pred_speakers:
        target_arrival = torch.full((labels.shape[0], num_pred_speakers), labels.shape[1], device=labels.device, dtype=sorted_arrival.dtype)
        target_arrival[:, :num_label_speakers] = sorted_arrival
    else:
        target_arrival = sorted_arrival[:, :num_pred_speakers]
    assignment_mask = torch.abs(arrival.unsqueeze(2) - target_arrival.unsqueeze(1)) <= tolerance
    return get_pil_targets_hungarian(labels, preds, assignment_mask=assignment_mask)

def get_frame_targets_from_rttm(rttm_timestamps: list, offset: float, duration: float, round_digits: int, feat_per_sec: int, max_spks: int, dtype: torch.dtype=torch.float32) -> torch.Tensor:
    """
    Create a multi-dimensional vector sequence containing speaker timestamp information in RTTM.
    The unit-length is the frame shift length of the acoustic feature. The feature-level annotations
    `feat_level_target` will later be converted to base-segment level diarization label.

    Args:
        rttm_timestamps (list): Lists of start times, end times, and speaker indices for the RTTM segments.
        offset (float): Start time of the selected audio region in seconds.
        duration (float): Duration of the selected audio region in seconds.
        round_digits (int): Decimal precision associated with the prepared RTTM timestamps.
        feat_per_sec (int): Number of feature frames per second, as determined by the preprocessing window stride.
        max_spks (int): Maximum number of target speakers. Use ``-1`` to preserve all speakers.
        dtype (torch.dtype): Output target dtype.

    Returns:
        feat_level_target (torch.Tensor): Speaker labels for each feature-level frame.
    """
    stt_list, end_list, speaker_list = rttm_timestamps
    sorted_speakers = sorted(list(set(speaker_list)))
    total_fr_len = int(duration * feat_per_sec)
    if max_spks == -1:
        num_target_speakers = max(1, len(sorted_speakers))
    else:
        num_target_speakers = max_spks
    if max_spks != -1 and len(sorted_speakers) > max_spks:
        logging.warning(f'Number of speakers in RTTM file {len(sorted_speakers)} exceeds the maximum number of speakers: {max_spks}! Only {max_spks} first speakers remain, and this will affect frame metrics!')
    feat_level_target = torch.zeros(total_fr_len, num_target_speakers, dtype=dtype)
    for count, (stt, end, spk_rttm_key) in enumerate(zip(stt_list, end_list, speaker_list)):
        if end < offset or stt > offset + duration:
            continue
        stt, end = (max(offset, stt), min(offset + duration, end))
        spk = spk_rttm_key
        if spk < num_target_speakers:
            stt_fr, end_fr = (int((stt - offset) * feat_per_sec), int((end - offset) * feat_per_sec))
            feat_level_target[stt_fr:end_fr, spk] = 1
    return feat_level_target

class ActivityLoss(torch.nn.Module):

    def __init__(self) -> None:
        """Initialize the activity loss with fixed valid-frame mean reduction."""
        super().__init__()

    def forward(self, activity_logits: torch.Tensor, targets: torch.Tensor, target_lens: torch.Tensor) -> torch.Tensor:
        """Calculate three-class cross-entropy after excluding padded frames.

        Args:
            activity_logits: Raw activity logits with shape ``(B, T, C)``.
            targets: Unpermuted speaker targets with shape ``(B, T, S)``.
            target_lens: Number of valid frames per batch item with shape ``(B,)``.

        Returns:
            Mean cross-entropy over valid frames as an FP32 scalar.
        """
        activity_targets = (targets > 0.5).sum(dim=-1).clamp(max=2).long()
        valid_frames = torch.arange(activity_logits.shape[1], device=activity_logits.device).unsqueeze(0) < target_lens.to(activity_logits.device).unsqueeze(1)
        with torch.autocast(device_type=activity_logits.device.type, enabled=False):
            frame_losses = F.cross_entropy(activity_logits.float().transpose(1, 2), activity_targets, reduction='none')
            loss = (frame_losses * valid_frames).sum() / valid_frames.sum().clamp_min(1).float()
        return loss

class PhantomLoss(torch.nn.Module):

    def __init__(self, threshold: float=0.25, temperature: float=0.5) -> None:
        """Initialize the phantom loss.

        Args:
            threshold: Detached speaker probability above which an eligible frame
                is selected. Must be finite and in ``[0, 1)``.
            temperature: Positive finite temperature for normalized log-mean-exp.

        Raises:
            TypeError: If either setting is not a numeric value or is a boolean.
            ValueError: If either setting is non-finite or outside its valid range.
        """
        super().__init__()
        if isinstance(threshold, bool) or not isinstance(threshold, Real):
            raise TypeError(f'threshold must be a finite numeric value in [0, 1), got {type(threshold).__name__}')
        self.threshold = float(threshold)
        if not math.isfinite(self.threshold) or not 0.0 <= self.threshold < 1.0:
            raise ValueError(f'threshold must be a finite numeric value in [0, 1), got {self.threshold}')
        if isinstance(temperature, bool) or not isinstance(temperature, Real):
            raise TypeError(f'temperature must be a finite positive numeric value, got {type(temperature).__name__}')
        self.temperature = float(temperature)
        if not math.isfinite(self.temperature) or self.temperature <= 0.0:
            raise ValueError(f'temperature must be a finite positive numeric value, got {self.temperature}')

    def forward(self, logits: torch.Tensor, phantom_targets: torch.Tensor, target_lens: torch.Tensor) -> torch.Tensor:
        """Calculate phantom loss over selected frames in empty target channels.

        Args:
            logits: Raw speaker logits with shape ``(B, T, S)``.
            phantom_targets: Aligned targets used to detect empty channels, with
                shape ``(B, T, S)``.
            target_lens: Number of valid frames per batch item with shape ``(B,)``.

        Returns:
            The FP32 batch-mean phantom loss.
        """
        num_frames, num_spks = (logits.shape[1], logits.shape[2])
        if num_frames == 0:
            return logits.float().sum() * 0.0
        valid_frames = torch.arange(num_frames, device=logits.device).unsqueeze(0) < target_lens.to(logits.device).unsqueeze(1)
        valid_frame_mask = valid_frames.unsqueeze(-1)
        target_empty_channels = ~((phantom_targets > 0.5) & valid_frame_mask).any(dim=1)
        detached_probs = torch.sigmoid(logits.detach())
        selected_phantom_frames = valid_frame_mask & target_empty_channels.unsqueeze(1) & (detached_probs > self.threshold)
        with torch.autocast(device_type=logits.device.type, enabled=False):
            negative_bce = F.softplus(logits.float())
            selected_frame_count = selected_phantom_frames.sum(dim=1)
            scaled_negative_bce = negative_bce / self.temperature
            selected_scaled_bce = scaled_negative_bce.masked_fill(~selected_phantom_frames, float('-inf'))
            has_selected_frames = selected_frame_count > 0
            safe_first_frame = torch.where(has_selected_frames.unsqueeze(1), selected_scaled_bce[:, :1, :], torch.zeros_like(selected_scaled_bce[:, :1, :]))
            selected_scaled_bce = torch.cat((safe_first_frame, selected_scaled_bce[:, 1:, :]), dim=1)
            per_channel_loss = self.temperature * (torch.logsumexp(selected_scaled_bce, dim=1) - torch.log(selected_frame_count.clamp_min(1).to(negative_bce.dtype)))
            per_channel_loss = torch.where(has_selected_frames, per_channel_loss, torch.zeros_like(per_channel_loss))
            phantom_loss = (per_channel_loss.sum(dim=1) / num_spks).mean()
        return phantom_loss

class BCEWithLogitsLoss(torch.nn.Module):

    def __init__(self, reduction: str='mean', pos_weight: Optional[Union[torch.Tensor, float, Sequence[float]]]=None) -> None:
        """Initialize the fused logits-based BCE loss.

        Args:
            reduction: Reduction applied by ``torch.nn.BCEWithLogitsLoss``.
                Supported values are ``"none"``, ``"mean"``, and ``"sum"``.
            pos_weight: Optional weight applied to positive examples.
                ``None`` is unweighted and adds no persistent state. Non-tensor
                values are converted to floating-point tensors.
        """
        super().__init__()
        if pos_weight is not None and (not torch.is_tensor(pos_weight)):
            pos_weight = torch.as_tensor(pos_weight, dtype=torch.float)
        self.loss_f = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight, reduction=reduction)

    def forward(self, logits: torch.Tensor, labels: torch.Tensor, target_lens: torch.Tensor) -> torch.Tensor:
        """Calculate logits-based BCE after excluding padded frames.

        Args:
            logits: Raw speaker logits with shape ``(B, T, C)``.
            labels: Binary speaker targets with shape ``(B, T, C)``.
            target_lens: Number of valid temporal frames per batch item with
                shape ``(B,)``.

        Returns:
            The fused BCE-with-logits loss with the configured reduction.
        """
        logits = torch.cat([logits[k, :target_lens[k], :] for k in range(logits.shape[0])], dim=0)
        labels = torch.cat([labels[k, :target_lens[k], :] for k in range(labels.shape[0])], dim=0)
        with torch.autocast(device_type=logits.device.type, enabled=False):
            loss = self.loss_f(logits.float(), labels.float())
        return loss
