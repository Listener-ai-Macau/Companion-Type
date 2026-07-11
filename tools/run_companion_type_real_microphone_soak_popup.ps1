param(
    [int]$Seconds = 3600
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Show-CompanionMessage {
    param(
        [string]$Title,
        [string]$Message,
        [System.Windows.Forms.MessageBoxButtons]$Buttons = [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]$Icon = [System.Windows.Forms.MessageBoxIcon]::Information
    )

    [System.Media.SystemSounds]::Asterisk.Play()
    return [System.Windows.Forms.MessageBox]::Show($Message, $Title, $Buttons, $Icon)
}

if ($Seconds -le 0) {
    throw "Seconds must be positive."
}

$minutes = [Math]::Round($Seconds / 60, 1)
$start = Show-CompanionMessage `
    -Title "Companion 真实麦克风长录音验证" `
    -Buttons ([System.Windows.Forms.MessageBoxButtons]::OKCancel) `
    -Icon ([System.Windows.Forms.MessageBoxIcon]::Information) `
    -Message "准备开始 Companion-Type 真实麦克风 soak。`r`n`r`n时长：$Seconds 秒（约 $minutes 分钟）。`r`n`r`n点击“确定”后请保持电脑麦克风可用，不要关闭这个终端；结束后会再弹窗提示结果。`r`n`r`n这是弹窗提示，不会打开记事本。"

if ($start -ne [System.Windows.Forms.DialogResult]::OK) {
    Show-CompanionMessage -Title "Companion 验证已取消" -Message "未开始真实麦克风 soak。"
    exit 2
}

$env:COMPANION_TYPE_REAL_MIC_SOAK_SECONDS = [string]$Seconds
$logDir = Join-Path (Get-Location) "docs\validation"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "companion-type-real-microphone-soak-popup.log"

$startedAt = Get-Date
try {
    & npm.cmd run verify:real-microphone-soak 2>&1 | Tee-Object -FilePath $logPath
    $exitCode = $LASTEXITCODE
} finally {
    Remove-Item Env:\COMPANION_TYPE_REAL_MIC_SOAK_SECONDS -ErrorAction SilentlyContinue
}
$endedAt = Get-Date
$elapsed = [Math]::Round(($endedAt - $startedAt).TotalMinutes, 1)

if ($exitCode -eq 0) {
    Show-CompanionMessage `
        -Title "Companion 真实麦克风验证完成" `
        -Icon ([System.Windows.Forms.MessageBoxIcon]::Information) `
        -Message "真实麦克风 soak 已完成。`r`n`r`n耗时：$elapsed 分钟。`r`n证据：docs\validation\companion-type-real-microphone-soak.json`r`n日志：$logPath"
} else {
    Show-CompanionMessage `
        -Title "Companion 真实麦克风验证失败" `
        -Icon ([System.Windows.Forms.MessageBoxIcon]::Error) `
        -Message "真实麦克风 soak 未通过。`r`n`r`n退出码：$exitCode`r`n日志：$logPath"
}

exit $exitCode
