<#
.SYNOPSIS
显示一个紧凑的人工记录采集窗口。

.DESCRIPTION
只在必须让人实时查看、操作或记录备注时使用。机器证据先完成，再用这个窗口采集
最终人工判断和备注。
#>

param(
    [string]$Title = "Operator prompt",
    [string]$Message = "",
    [string]$DefaultText = "",
    [string]$Buttons = "Submit,Cancel",
    # Non-submitting auxiliary buttons (comma list). Each click only appends an
    # `action_button|<label>` event to EventPath and keeps the popup open —
    # used for in-popup stimulus control (e.g. 干扰播放 开始/停止) where a
    # headless watcher process reacts to the event stream.
    [string]$ActionButtons = "",
    [string]$OutputPath = "",
    [string]$EventPath = "",
    [string]$UpdatePath = "",
    [switch]$LiveUpdates,
    [string]$ProgressText = "",
    [string]$ScopeText = "",
    [string]$ExpectedText = "",
    [string]$SpokenText = "",
    [string]$ObservationLabel = "备注（可留空；有异常、疑问或小瑕疵就写下来，我会当作需求处理）",
    [Alias("Input")]
    [switch]$TextInput,
    [switch]$ReviewStyle,
    [switch]$RequireReviewAllowed,
    [switch]$Json,
    [switch]$NoSound,
    [switch]$NoActivate,
    [switch]$NoTopMost,
    [switch]$Help,
    [ValidateSet("Center", "TopLeft")]
    [string]$Position = "TopLeft",
    [int]$Width = 680,
    [int]$Height = 360,
    [int]$MessageHeight = 0,
    [int]$TimeoutSeconds = 0
)

$ErrorActionPreference = "Stop"

if ($Help.IsPresent) {
    @"
operator-prompt -Title <text> -Message <text> [options]

常用人工记录：
  operator-prompt -Title "人工确认" -ProgressText "2/20" -ScopeText "当前验收范围；有备注会进入 triage" -Message "请检查当前行为" -ExpectedText "符合已确认的产品合同" -Input -Buttons "通过,失败,跳过,中止" -OutputPath .cache\operator-prompt\observation.txt -Json

Options:
  -Input                 显示备注输入框。
  -ProgressText <x/y>    在标题区显示进度。
  -ScopeText <text>      在标题下显示当前范围。
  -ExpectedText <text>   在 ReviewStyle 下显示通过标准。
  -SpokenText <text>     在“请朗读的原文”专用只读框中显示原文。
  -ReviewStyle           未传 Buttons 时使用默认中文按钮。
  -TimeoutSeconds <n>    n 秒后自动关闭，selected=Timeout。
  -EventPath <path>      按钮确认后先写出一条结构化事件，再关闭窗口。
  -UpdatePath <path>     读取验收器更新；review_allowed 后启用完成按钮。
  -LiveUpdates          同一原窗口持续更新正文/进度和可用动作，不更换版式或重播提示音。
  -RequireReviewAllowed   在收到 review_allowed 前禁用“我已实际说完”。
  -MessageHeight <n>     指定步骤正文区域高度（像素）。
  -NoSound               不播放提示音。
  -NoActivate            显示提示窗但不抢占当前输入窗口焦点。
"@
    exit 0
}

$operatorPromptUi = Join-Path $PSScriptRoot "operator_prompt_ui.ps1"
. $operatorPromptUi

$Message = Convert-PromptEscapedNewlines -Text $Message
$DefaultText = Convert-PromptEscapedNewlines -Text $DefaultText
$ProgressText = Convert-PromptEscapedNewlines -Text $ProgressText
$ScopeText = Convert-PromptEscapedNewlines -Text $ScopeText
$ExpectedText = Convert-PromptEscapedNewlines -Text $ExpectedText
$SpokenText = Convert-PromptEscapedNewlines -Text $SpokenText
$ObservationLabel = Convert-PromptEscapedNewlines -Text $ObservationLabel

Add-Type -AssemblyName System.Windows.Forms | Out-Null
Add-Type -AssemblyName System.Drawing | Out-Null

if ($NoActivate -and -not ("ListenerNoActivateEditablePromptFormV2" -as [type])) {
    $formsAssembly = [System.Windows.Forms.Form].Assembly.Location
    $formsPrimitivesAssembly = Join-Path (
        Split-Path -Parent $formsAssembly
    ) 'System.Windows.Forms.Primitives.dll'
    Add-Type -TypeDefinition @'
using System;
using System.Windows.Forms;
using System.Runtime.InteropServices;

public sealed class ListenerNoActivateEditablePromptFormV2 : Form
{
    public bool AllowUserActivation { get; set; }
    [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")]
    private static extern IntPtr GetWindowLongPtr64(IntPtr hwnd, int index);
    [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW")]
    private static extern IntPtr SetWindowLongPtr64(IntPtr hwnd, int index, IntPtr value);
    [DllImport("user32.dll", EntryPoint = "GetWindowLongW")]
    private static extern int GetWindowLong32(IntPtr hwnd, int index);
    [DllImport("user32.dll", EntryPoint = "SetWindowLongW")]
    private static extern int SetWindowLong32(IntPtr hwnd, int index, int value);
    protected override bool ShowWithoutActivation { get { return true; } }

    private void PermitExplicitMouseActivation()
    {
        // The native style protects initial display. Release it only in direct
        // response to this editable prompt's actual WM_MOUSEACTIVATE request.
        if (IntPtr.Size == 8) {
            long style = GetWindowLongPtr64(Handle, -20).ToInt64();
            SetWindowLongPtr64(Handle, -20, new IntPtr(style & ~0x08000000L));
        } else {
            int style = GetWindowLong32(Handle, -20);
            SetWindowLong32(Handle, -20, style & ~0x08000000);
        }
    }

    protected override CreateParams CreateParams
    {
        get
        {
            CreateParams parameters = base.CreateParams;
            // ShowWithoutActivation already keeps initial display passive.
            // An editable prompt must activate normally when Owner clicks it;
            // WS_EX_NOACTIVATE also suppresses that explicit mouse activation.
            if (!AllowUserActivation) parameters.ExStyle |= 0x08000000;
            return parameters;
        }
    }

    protected override void WndProc(ref Message message)
    {
        if (message.Msg == 0x0021) // WM_MOUSEACTIVATE
        {
            if (AllowUserActivation) {
                PermitExplicitMouseActivation();
                message.Result = (IntPtr)1; // MA_ACTIVATE: user explicitly clicked
            } else {
                message.Result = (IntPtr)3; // MA_NOACTIVATE: passive prompt
            }
            return;
        }
        base.WndProc(ref message);
    }
}
'@ -ReferencedAssemblies @(
        $formsAssembly,
        $formsPrimitivesAssembly,
        [System.ComponentModel.Component].Assembly.Location
    )
}

if ($ReviewStyle.IsPresent -and -not $PSBoundParameters.ContainsKey("Buttons")) {
    $Buttons = "通过,失败,跳过,中止"
}

$hasSpokenText = -not [string]::IsNullOrWhiteSpace($SpokenText)
$reviewLayout = $ReviewStyle.IsPresent -and $TextInput -and -not [string]::IsNullOrWhiteSpace($ExpectedText)
$minimumClientHeight = if ($TextInput -and $hasSpokenText -and $reviewLayout) {
    540
} elseif ($TextInput -and $hasSpokenText) {
    440
} elseif ($TextInput -and $reviewLayout) {
    340
} elseif ($TextInput) {
    340
} elseif ($hasSpokenText) {
    280
} else {
    340
}

$buttonLabels = @(
    $Buttons -split "," |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -ne "" }
)
if ($buttonLabels.Count -eq 0) {
    $buttonLabels = @("Submit", "Cancel")
}
$actionLabels = @(
    $ActionButtons -split "," |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -ne "" }
)

$form = if ($NoActivate) {
    New-Object ListenerNoActivateEditablePromptFormV2
} else {
    New-Object System.Windows.Forms.Form
}
if ($NoActivate) { $form.AllowUserActivation = $TextInput.IsPresent }
$windowProgress = if ([string]::IsNullOrWhiteSpace($ProgressText)) { "" } else { " $ProgressText" }
$form.Text = "$Title$windowProgress"
$form.StartPosition = if ($Position -eq "TopLeft") {
    [System.Windows.Forms.FormStartPosition]::Manual
} else {
    [System.Windows.Forms.FormStartPosition]::CenterScreen
}
$form.TopMost = -not $NoTopMost
$form.ClientSize = New-Object System.Drawing.Size(
    [Math]::Max(640, $Width),
    [Math]::Max($minimumClientHeight, $Height)
)
$form.MinimumSize = New-Object System.Drawing.Size(640, $minimumClientHeight)
$form.MaximizeBox = $false
$form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::Dpi
$form.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10)
if ($Position -eq "TopLeft") {
    $workingArea = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $form.Location = New-Object System.Drawing.Point(
        [Math]::Max($workingArea.Left + 12, $workingArea.Left),
        [Math]::Max($workingArea.Top + 72, $workingArea.Top)
    )
}

$contentLeft = 16
$contentWidth = $form.ClientSize.Width - 32

$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = if ([string]::IsNullOrWhiteSpace($ProgressText)) {
    $Title
} else {
    "$ProgressText  $Title"
}
$titleLabel.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 12, [System.Drawing.FontStyle]::Bold)
$titleLabel.AutoSize = $false
$titleLabel.Location = New-Object System.Drawing.Point($contentLeft, 10)
$titleLabel.Size = New-Object System.Drawing.Size($contentWidth, 26)
$titleLabel.Anchor = [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
$form.Controls.Add($titleLabel)

$scopeLabel = New-Object System.Windows.Forms.Label
$scopeLabel.Text = if ([string]::IsNullOrWhiteSpace($ScopeText)) {
    "你现在做"
} else {
    "你现在做 - $ScopeText"
}
$scopeLabel.AutoSize = $false
$scopeLabel.Location = New-Object System.Drawing.Point($contentLeft, 42)
$scopeLabel.Size = New-Object System.Drawing.Size($contentWidth, 20)
$scopeLabel.Anchor = [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
$form.Controls.Add($scopeLabel)

$buttonPanel = New-Object System.Windows.Forms.FlowLayoutPanel
$buttonPanel.FlowDirection = [System.Windows.Forms.FlowDirection]::RightToLeft
$buttonPanel.WrapContents = $false
$buttonPanel.Location = New-Object System.Drawing.Point($contentLeft, ($form.ClientSize.Height - 42))
$buttonPanel.Size = New-Object System.Drawing.Size($contentWidth, 34)
$buttonPanel.Anchor = [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Right -bor [System.Windows.Forms.AnchorStyles]::Bottom

$messageBox = New-Object System.Windows.Forms.TextBox
$messageBox.Multiline = $true
$messageBox.ReadOnly = $true
$messageBox.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
$messageBox.Location = New-Object System.Drawing.Point($contentLeft, 64)
$messageBoxHeight = if ($MessageHeight -gt 0) {
    $MessageHeight
} elseif ($hasSpokenText) {
    54
} elseif ($reviewLayout) {
    72
} elseif ($TextInput) {
    116
} else {
    $form.ClientSize.Height - 120
}
$messageBox.Size = New-Object System.Drawing.Size($contentWidth, $messageBoxHeight)
$messageBox.Anchor = [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
$messageBox.Text = $Message
$form.Controls.Add($messageBox)

$observationLabelControl = $null
$nextControlTop = 64 + $messageBoxHeight + 8

if ($hasSpokenText) {
    $spokenLabel = New-Object System.Windows.Forms.Label
    $spokenLabel.Text = "请朗读的原文"
    $spokenLabel.AutoSize = $false
    $spokenLabel.Location = New-Object System.Drawing.Point($contentLeft, $nextControlTop)
    $spokenLabel.Size = New-Object System.Drawing.Size($contentWidth, 20)
    $spokenLabel.Anchor = [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
    $spokenLabel.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10, [System.Drawing.FontStyle]::Bold)
    $form.Controls.Add($spokenLabel)

    $spokenBox = New-Object System.Windows.Forms.TextBox
    $spokenBox.Multiline = $true
    $spokenBox.ReadOnly = $true
    $spokenBox.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
    $spokenBox.Location = New-Object System.Drawing.Point($contentLeft, ($nextControlTop + 22))
    $spokenBox.Size = New-Object System.Drawing.Size($contentWidth, 96)
    $spokenBox.Anchor = [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
    $spokenBox.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 11)
    $spokenBox.Text = $SpokenText
    $form.Controls.Add($spokenBox)
    $nextControlTop += 126
}

$textBox = $null
if ($TextInput) {
    $expectedLabelControl = $null
    $expectedBox = $null
    if ($reviewLayout) {
        $expectedLabelControl = New-Object System.Windows.Forms.Label
        $expectedLabelControl.Text = "通过标准"
        $expectedLabelControl.AutoSize = $false
        $expectedLabelControl.Location = New-Object System.Drawing.Point($contentLeft, $nextControlTop)
        $expectedLabelControl.Size = New-Object System.Drawing.Size($contentWidth, 20)
        $expectedLabelControl.Anchor = [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
        $form.Controls.Add($expectedLabelControl)

        $expectedBox = New-Object System.Windows.Forms.TextBox
        $expectedBox.Multiline = $true
        $expectedBox.ReadOnly = $true
        $expectedBox.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
        $expectedBox.Location = New-Object System.Drawing.Point($contentLeft, ($nextControlTop + 22))
        $expectedBox.Size = New-Object System.Drawing.Size($contentWidth, 62)
        $expectedBox.Anchor = [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
        $expectedBox.Text = $ExpectedText
        $form.Controls.Add($expectedBox)
        $nextControlTop += 84
    }

    $observationLabelControl = New-Object System.Windows.Forms.Label
    $observationLabelControl.Text = $ObservationLabel
    $observationLabelControl.AutoSize = $false
    $observationLabelControl.Location = New-Object System.Drawing.Point($contentLeft, $nextControlTop)
    $observationLabelControl.Size = New-Object System.Drawing.Size($contentWidth, 20)
    $observationLabelControl.Anchor = [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
    $form.Controls.Add($observationLabelControl)

    $textBox = New-Object System.Windows.Forms.TextBox
    $textBox.Multiline = $true
    $textBox.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
    $textBox.AcceptsReturn = $true
    $textBox.AcceptsTab = $true
    $textBox.ReadOnly = $false
    $textBox.Enabled = $true
    $textBox.TabStop = $true
    $textBox.ShortcutsEnabled = $true
    $textBox.Location = New-Object System.Drawing.Point($contentLeft, ($nextControlTop + 22))
    $textBox.Size = New-Object System.Drawing.Size(
        $contentWidth,
        [Math]::Max(52, ($form.ClientSize.Height - ($nextControlTop + 76)))
    )
    $textBox.Anchor = [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right -bor [System.Windows.Forms.AnchorStyles]::Bottom
    $textBox.Text = $DefaultText
    $form.Controls.Add($textBox)
}

$script:selected = "Cancel"
$script:text = $DefaultText
$script:outputSaved = $false
$script:reviewEventWritten = $false
$script:closedEventWritten = $false
$script:reviewAllowed = -not $RequireReviewAllowed

function Save-OperatorPromptResult {
    if ($textBox -ne $null) {
        $script:text = $textBox.Text
    }
    if ($OutputPath -ne "" -and -not $script:outputSaved) {
        $parent = Split-Path -Parent $OutputPath
        if ($parent -and -not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
        }
        Set-Content -LiteralPath $OutputPath -Value $script:text -Encoding UTF8
        $script:outputSaved = $true
    }
}

function Write-OperatorPromptEvent {
    param([Parameter(Mandatory = $true)][string]$Event)
    if ([string]::IsNullOrWhiteSpace($EventPath)) {
        return
    }
    if ($Event -eq 'review_submitted' -and $script:reviewEventWritten) { return }
    if ($Event -eq 'popup_closed' -and $script:closedEventWritten) { return }
    $parent = Split-Path -Parent $EventPath
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    # Forensics (r22): the operator said the action buttons were invisible; the
    # event log had no way to show where the window actually rendered.
    $windowBounds = $null
    try {
        if ($form -and -not $form.IsDisposed) {
            $windowBounds = "{0},{1},{2},{3}" -f $form.Bounds.X, $form.Bounds.Y, $form.Bounds.Width, $form.Bounds.Height
        }
    } catch { }
    $record = [ordered]@{
        schema = "listener.operator-prompt-event.v1"
        event = $Event
        at = [DateTime]::UtcNow.ToString("o")
        selected = $script:selected
        text = $script:text
        spoken_text = if ($hasSpokenText) { $SpokenText } else { $null }
        output_path = if ($OutputPath -ne "") { $OutputPath } else { $null }
        window_bounds = $windowBounds
        processId = [int]$PID
        window_active = [bool]($form -and $form.ContainsFocus)
        input_focused = [bool]($textBox -and $textBox.Focused)
    }
    $writer = [System.IO.StreamWriter]::new(
        $EventPath,
        $true,
        [System.Text.UTF8Encoding]::new($false))
    try {
        $writer.WriteLine(($record | ConvertTo-Json -Compress -Depth 8))
        $writer.Flush()
    } finally {
        $writer.Dispose()
    }
    if ($Event -eq 'review_submitted') { $script:reviewEventWritten = $true }
    if ($Event -eq 'popup_closed') { $script:closedEventWritten = $true }
}

$reviewButtons = [System.Collections.Generic.List[object]]::new()
foreach ($label in $buttonLabels) {
    $button = New-PromptButton -Text $label
    if ($RequireReviewAllowed -and $label -in @('我已实际说完', '通过', '文字已出现')) {
        $button.Enabled = $false
        [void]$reviewButtons.Add($button)
    }
    $button.Add_Click({
        if (-not $script:reviewAllowed -and ($reviewButtons -contains $this)) {
            return
        }
        $script:selected = $this.Text
        Save-OperatorPromptResult
        Write-OperatorPromptEvent -Event "review_submitted"
        $form.Close()
    })
    [void]$buttonPanel.Controls.Add($button)
}
$form.Controls.Add($buttonPanel)

# Auxiliary action buttons live on the same bottom row, left-aligned so they
# never crowd the review buttons (RTL flow keeps those at the right edge). A
# click only records an event; it must not submit, close, or touch the review
# text.
# r22 postmortem: Controls.Add puts later controls BEHIND earlier ones in the
# WinForms z-order, and the full-width review buttonPanel paints an opaque
# background across the whole bottom row — the action buttons existed but were
# completely occluded ("没看见"). So size this panel to its content (left strip
# only) and BringToFront so it renders above the review panel's background.
$runtimeActionButtons = [System.Collections.Generic.List[object]]::new()
if ($actionLabels.Count -gt 0) {
    $actionPanel = New-Object System.Windows.Forms.FlowLayoutPanel
    $actionPanel.FlowDirection = [System.Windows.Forms.FlowDirection]::LeftToRight
    $actionPanel.WrapContents = $false
    $actionPanel.Location = New-Object System.Drawing.Point($contentLeft, ($form.ClientSize.Height - 42))
    $actionPanel.Size = New-Object System.Drawing.Size((($actionLabels.Count * 158) + 8), 34)
    $actionPanel.Anchor = [System.Windows.Forms.AnchorStyles]::Left -bor [System.Windows.Forms.AnchorStyles]::Bottom
    foreach ($actionLabel in $actionLabels) {
        $actionButton = New-PromptButton -Text $actionLabel
        $actionButton.Width = 150
        if ($LiveUpdates) { $actionButton.Enabled = $false }
        [void]$runtimeActionButtons.Add($actionButton)
        $actionButton.Add_Click({
            # The user clicked this window. Move focus within that same form
            # before publishing readiness; do not activate another application.
            if ($textBox -and $form.ContainsFocus) {
                $form.ActiveControl = $textBox
                [void]$textBox.Focus()
                $textBox.SelectionStart = $textBox.TextLength
            }
            Write-OperatorPromptEvent -Event ("action_button|" + $this.Text)
        })
        [void]$actionPanel.Controls.Add($actionButton)
    }
    $form.Controls.Add($actionPanel)
    $actionPanel.BringToFront()
}
$form.Add_Shown({
    if ($form.WindowState -eq [System.Windows.Forms.FormWindowState]::Minimized) {
        $form.WindowState = [System.Windows.Forms.FormWindowState]::Normal
    }
    if (-not $NoActivate) {
        $form.BringToFront()
        Invoke-OperatorPromptFlash -Handle $form.Handle
    }
    Invoke-OperatorPromptCue
    if ($textBox -ne $null -and -not $NoActivate) {
        [void]$form.BeginInvoke([System.Action]{
            $form.Activate()
            $form.ActiveControl = $textBox
            $textBox.Focus()
            $textBox.SelectAll()
        })
    } elseif (-not $NoActivate) {
        $form.Activate()
        [void]$form.Focus()
    }
})
$form.Add_FormClosing({
    Save-OperatorPromptResult
})
$form.Add_FormClosed({
    Write-OperatorPromptEvent -Event "popup_closed"
})

$timeoutTimer = $null
if ($TimeoutSeconds -gt 0) {
    $timeoutTimer = New-Object System.Windows.Forms.Timer
    $timeoutTimer.Interval = [Math]::Max(1, $TimeoutSeconds) * 1000
    $timeoutTimer.Add_Tick({
        $timeoutTimer.Stop()
        $script:selected = "Timeout"
        Save-OperatorPromptResult
        $form.Close()
    })
    $timeoutTimer.Start()
}

function Set-OperatorPromptLiveUpdate {
    param([Parameter(Mandatory = $true)]$Update)
    # A continuous use can return from review to the normal product. Respect
    # an explicit false as well as true; reopening is not a final submission.
    if ($null -ne $Update.PSObject.Properties['reviewAllowed']) {
        $script:reviewAllowed = [bool]$Update.reviewAllowed
        foreach ($reviewButton in $reviewButtons) {
            $reviewButton.Enabled = $script:reviewAllowed
        }
    }
    if ($null -ne $Update.message) {
        $updatedMessage = Convert-PromptEscapedNewlines -Text ([string]$Update.message)
        if ($messageBox.Text -ne $updatedMessage) { $messageBox.Text = $updatedMessage }
    }
    if ($null -ne $Update.progressText) {
        $titleLabel.Text = "{0}  {1}" -f [string]$Update.progressText, $Title
        $form.Text = "{0} {1}" -f $Title, [string]$Update.progressText
    }
    if ($null -ne $Update.enabledActions) {
        $enabled = @($Update.enabledActions)
        foreach ($actionControl in $runtimeActionButtons) {
            $actionControl.Enabled = $enabled -contains $actionControl.Text
        }
    }
    # A live controller may observe completion itself. This is a controller
    # result, never a fabricated user click or submitted review.
    if ($Update.closeRequested -eq $true) {
        $script:selected = "ObservedComplete"
        Write-OperatorPromptEvent -Event "controller_observed_complete"
        $form.Close()
    }
}
$reviewAllowedTimer = $null
if (($RequireReviewAllowed -or $LiveUpdates) -and -not [string]::IsNullOrWhiteSpace($UpdatePath)) {
    $reviewAllowedTimer = New-Object System.Windows.Forms.Timer
    $reviewAllowedTimer.Interval = 150
    $reviewAllowedTimer.Add_Tick({
        if ($script:reviewAllowed -and -not $LiveUpdates) { return }
        try {
            if (-not (Test-Path -LiteralPath $UpdatePath)) { return }
            $update = Get-Content -LiteralPath $UpdatePath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($LiveUpdates) { Set-OperatorPromptLiveUpdate -Update $update }
            if ([bool]$update.reviewAllowed -or ($null -eq $update.PSObject.Properties['reviewAllowed'] -and [string]$update.stage -eq 'review_allowed')) {
                $script:reviewAllowed = $true
                foreach ($reviewButton in $reviewButtons) { $reviewButton.Enabled = $true }
                if (-not $LiveUpdates) { $reviewAllowedTimer.Stop() }
            }
        } catch { }
    })
    $reviewAllowedTimer.Start()
}

[void]$form.ShowDialog()
if ($timeoutTimer -ne $null) {
    $timeoutTimer.Stop()
    $timeoutTimer.Dispose()
}
if ($reviewAllowedTimer -ne $null) {
    $reviewAllowedTimer.Stop()
    $reviewAllowedTimer.Dispose()
}

$result = [PSCustomObject][ordered]@{
    selected = $script:selected
    text = $script:text
    spoken_text = if ($hasSpokenText) { $SpokenText } else { $null }
    output_path = if ($OutputPath -ne "") { $OutputPath } else { $null }
}

if ($Json) {
    $result | ConvertTo-Json -Depth 4
} else {
    Write-Output "selected=$($result.selected)"
    if ($TextInput) {
        Write-Output "text=$($result.text)"
    }
    if ($result.output_path) {
        Write-Output "output_path=$($result.output_path)"
    }
}
