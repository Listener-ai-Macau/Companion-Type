param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [int]$PromptTimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Get-FileEvidence {
    param([string]$RelativePath)

    $fullPath = Join-Path $RepoRoot $RelativePath
    return [pscustomobject]@{
        path = $RelativePath
        fullPath = $fullPath
        exists = Test-Path -LiteralPath $fullPath
        bytes = if (Test-Path -LiteralPath $fullPath) { (Get-Item -LiteralPath $fullPath).Length } else { 0 }
    }
}

function New-ChecklistItem {
    param(
        [string]$Text,
        [int]$Y
    )

    $box = New-Object System.Windows.Forms.CheckBox
    $box.Text = $Text
    $box.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10)
    $box.AutoSize = $false
    $box.Location = New-Object System.Drawing.Point(28, $Y)
    $box.Size = New-Object System.Drawing.Size(800, 44)
    return $box
}

function Show-FinalSignoffPrompt {
    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Companion-Type 最终人工确认"
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(880, 560)
    $form.TopMost = $true
    $form.MinimizeBox = $false
    $form.MaximizeBox = $false
    $form.FormBorderStyle = "FixedDialog"

    $title = New-Object System.Windows.Forms.Label
    $title.Text = "请只在你已经真实检查后勾选并确认。"
    $title.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 14, [System.Drawing.FontStyle]::Bold)
    $title.AutoSize = $false
    $title.Location = New-Object System.Drawing.Point(24, 22)
    $title.Size = New-Object System.Drawing.Size(820, 34)

    $body = New-Object System.Windows.Forms.Label
    $body.Text = "这个弹窗用于 Companion 1/2 最终人工 gate。AI 已有自动化证据；你负责最终物理链条确认。没有实际看过/听过就点[稍后确认]。"
    $body.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10)
    $body.AutoSize = $false
    $body.Location = New-Object System.Drawing.Point(28, 64)
    $body.Size = New-Object System.Drawing.Size(805, 52)

    $checks = [ordered]@{
        physicalBoard = New-ChecklistItem -Text "真实 Companion 开发板连接正常，板上状态和硬件链路看起来符合预期。" -Y 126
        sw3ButtonChain = New-ChecklistItem -Text "SW3/B3 按键录音链路最终确认无误：按下/松开行为与录音开始/停止预期一致。" -Y 176
        realMicrophoneVoice = New-ChecklistItem -Text "录音声源是真实麦克风/真实人声，不是纯模拟或旧文件冒充。" -Y 226
        installedUiImport = New-ChecklistItem -Text "安装版 Companion Type 已显示真实设备导入结果：Connected、synced、Captured、Recordings 归零或等价结果。" -Y 276
        noListenerTypeRuntime = New-ChecklistItem -Text "本次 Companion 验收没有依赖 Listener-Type 运行时，也没有要求修改 Listener-Type。" -Y 326
    }

    $status = New-Object System.Windows.Forms.Label
    $status.Text = "全部勾选后才能确认通过。超时或稍后会写 PENDING，不会算作通过。"
    $status.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 9)
    $status.AutoSize = $false
    $status.Location = New-Object System.Drawing.Point(28, 388)
    $status.Size = New-Object System.Drawing.Size(805, 28)

    $pass = New-Object System.Windows.Forms.Button
    $pass.Text = "确认通过"
    $pass.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10)
    $pass.Location = New-Object System.Drawing.Point(474, 440)
    $pass.Size = New-Object System.Drawing.Size(110, 40)
    $pass.Add_Click({
        $missing = @($checks.GetEnumerator() | Where-Object { -not $_.Value.Checked } | ForEach-Object { $_.Key })
        if ($missing.Count -gt 0) {
            $status.Text = "还有未确认项，不能通过：$($missing -join ', ')"
            [System.Media.SystemSounds]::Exclamation.Play()
            return
        }
        $form.Tag = "PASS"
        $form.Close()
    })

    $fail = New-Object System.Windows.Forms.Button
    $fail.Text = "记录未通过"
    $fail.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10)
    $fail.Location = New-Object System.Drawing.Point(600, 440)
    $fail.Size = New-Object System.Drawing.Size(110, 40)
    $fail.Add_Click({
        $form.Tag = "FAIL_HUMAN_REJECTED"
        $form.Close()
    })

    $pending = New-Object System.Windows.Forms.Button
    $pending.Text = "稍后确认"
    $pending.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10)
    $pending.Location = New-Object System.Drawing.Point(726, 440)
    $pending.Size = New-Object System.Drawing.Size(110, 40)
    $pending.Add_Click({
        $form.Tag = "PENDING_HUMAN_SIGNOFF"
        $form.Close()
    })

    $form.Controls.Add($title)
    $form.Controls.Add($body)
    foreach ($box in $checks.Values) {
        $form.Controls.Add($box)
    }
    $form.Controls.Add($status)
    $form.Controls.Add($pass)
    $form.Controls.Add($fail)
    $form.Controls.Add($pending)

    $timer = $null
    if ($PromptTimeoutSeconds -gt 0) {
        $timer = New-Object System.Windows.Forms.Timer
        $timer.Interval = $PromptTimeoutSeconds * 1000
        $timer.Add_Tick({
            $timer.Stop()
            $form.Tag = "PENDING_TIMEOUT"
            $form.Close()
        })
        $timer.Start()
    }

    [System.Media.SystemSounds]::Exclamation.Play()
    try {
        [void]$form.ShowDialog()
    } finally {
        if ($timer) {
            $timer.Stop()
            $timer.Dispose()
        }
    }

    $result = if ($form.Tag) { [string]$form.Tag } else { "PENDING_CLOSED" }
    $checkState = [ordered]@{}
    foreach ($entry in $checks.GetEnumerator()) {
        $checkState[$entry.Key] = [bool]$entry.Value.Checked
    }
    $form.Dispose()

    return [pscustomobject]@{
        result = $result
        checks = [pscustomobject]$checkState
    }
}

$validationDir = Join-Path $RepoRoot "docs\validation"
New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
$summaryPath = Join-Path $validationDir "companion-type-final-human-signoff.json"

$prompt = Show-FinalSignoffPrompt
$artifact = [pscustomobject]@{
    schema = "companion_type.final_human_signoff.v1"
    generatedAt = (Get-Date).ToUniversalTime().ToString("o")
    result = $prompt.result
    operator = "local-human"
    checks = $prompt.checks
    evidence = @(
        Get-FileEvidence "docs\validation\companion-type-joint-acceptance.json"
        Get-FileEvidence "docs\validation\companion-type-installed-ui-sync.json"
        Get-FileEvidence "docs\validation\companion-type-installed-ui-sync-05-after-sync-settled.png"
        Get-FileEvidence "docs\validation\companion-type-native-ble-sync-popup.json"
        Get-FileEvidence "docs\validation\companion-type-real-microphone.json"
    )
    note = "PASS means a local human explicitly confirmed the final Companion physical and installed-app UI chain in the popup."
}

$artifact | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

if ($prompt.result -eq "PASS") {
    Write-Output "PASS Companion-Type final human signoff: $summaryPath"
    exit 0
}

Write-Output "$($prompt.result) Companion-Type final human signoff: $summaryPath"
exit 2
