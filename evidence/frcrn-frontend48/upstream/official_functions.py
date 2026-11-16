# Exact upstream function ASTs; no change to numerical operations.
import numpy as np
EPS = 1e-6

def decode_one_audio_frcrn_se_16k(model, device, inputs, args):
    """Decodes audio using the FRCRN model for speech enhancement at 16kHz.

    This function processes the input audio tensor either in segments or as a whole, 
    depending on the length of the input. The model's inference method is applied 
    to obtain the enhanced audio output.

    Args:
        model (nn.Module): The trained FRCRN model used for decoding.
        device (torch.device): The device (CPU or GPU) to perform computations on.
        inputs (torch.Tensor): Input audio tensor of shape (B, T), where B is the batch size
                              and T is the number of time steps.
        args (Namespace): Contains arguments for decoding configuration.

    Returns:
        numpy.ndarray: The decoded audio output, which has been enhanced by the model.
    """
    decode_do_segment = False
    window = int(args.sampling_rate * args.decode_window)
    stride = int(window * 0.75)
    b, t = inputs.shape
    if t > args.sampling_rate * args.one_time_decode_length:
        decode_do_segment = True
    if t < window:
        inputs = np.concatenate([inputs, np.zeros((inputs.shape[0], window - t))], axis=1)
    elif t < window + stride:
        padding = window + stride - t
        inputs = np.concatenate([inputs, np.zeros((inputs.shape[0], padding))], axis=1)
    elif (t - window) % stride != 0:
        padding = t - (t - window) // stride * stride
        inputs = np.concatenate([inputs, np.zeros((inputs.shape[0], padding))], axis=1)
    inputs = torch.from_numpy(np.float32(inputs)).to(device)
    b, t = inputs.shape
    if decode_do_segment:
        outputs = np.zeros(t)
        give_up_length = (window - stride) // 2
        current_idx = 0
        while current_idx + window <= t:
            tmp_input = inputs[:, current_idx:current_idx + window]
            tmp_output = model.inference(tmp_input).detach().cpu().numpy()
            if current_idx == 0:
                outputs[current_idx:current_idx + window - give_up_length] = tmp_output[:-give_up_length]
            else:
                outputs[current_idx + give_up_length:current_idx + window - give_up_length] = tmp_output[give_up_length:-give_up_length]
            current_idx += stride
    else:
        outputs = model.inference(inputs).detach().cpu().numpy()
    return outputs

def audio_norm(x):
    """
    Normalizes the input audio signal to a target Root Mean Square (RMS) level, 
    applying two stages of scaling. This ensures the audio signal is neither too quiet 
    nor too loud, keeping its amplitude consistent.

    Parameters:
    x (numpy.ndarray): Input audio signal to be normalized.

    Returns:
    numpy.ndarray: Normalized audio signal.
    """
    rms = (x ** 2).mean() ** 0.5
    scalar = 10 ** (-25 / 20) / (rms + EPS)
    x = x * scalar
    pow_x = x ** 2
    avg_pow_x = pow_x.mean()
    rmsx = pow_x[pow_x > avg_pow_x].mean() ** 0.5
    scalarx = 10 ** (-25 / 20) / (rmsx + EPS)
    x = x * scalarx
    return (x, 1 / (scalar * scalarx + EPS))
