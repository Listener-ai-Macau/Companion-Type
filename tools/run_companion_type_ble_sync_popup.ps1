param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$SerialPort = "",
    [int]$BaudRate = 115200,
    [double]$RecordSeconds = 2.0,
    [int]$ButtonTimeoutSeconds = 90,
    [int]$ScanTimeoutMs = 10000,
    [int]$NotifyTimeoutMs = 20000
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.IO.Ports

function Resolve-StLinkPort {
    param([string]$Requested)

    if ($Requested.Trim()) {
        return $Requested.Trim()
    }

    $ports = Get-CimInstance Win32_PnPEntity |
        Where-Object { $_.Name -match "\(COM\d+\)" -and ($_.Name -match "STMicroelectronics|STLink|ST-LINK" -or $_.PNPDeviceID -match "VID_0483") }
    if (@($ports).Count -ne 1) {
        $seen = ($ports | ForEach-Object { "$($_.Name) $($_.PNPDeviceID)" }) -join "; "
        throw "Expected exactly one ST-LINK serial port; found $(@($ports).Count). $seen"
    }

    if ($ports[0].Name -match "\((COM\d+)\)") {
        return $Matches[1]
    }
    throw "Could not parse COM port from $($ports[0].Name)"
}

function Open-SerialPort {
    param([string]$PortName, [int]$Baud)

    $serial = [System.IO.Ports.SerialPort]::new($PortName, $Baud, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One)
    $serial.ReadTimeout = 50
    $serial.DtrEnable = $false
    $serial.RtsEnable = $false
    $serial.Open()
    $serial.DtrEnable = $false
    $serial.RtsEnable = $false
    $serial.DiscardInBuffer()
    $serial.DiscardOutBuffer()
    return $serial
}

function Wait-Sw3PressReleasePopup {
    param(
        [System.IO.Ports.SerialPort]$Serial,
        [string]$Title,
        [string]$Instruction,
        [int]$TimeoutSeconds,
        [string]$RawLogPath,
        [string]$ExpectedRecordAction = "",
        [string]$ExpectedCompletionPattern = "",
        [string]$ExpectedCompletionLabel = ""
    )

    $state = [ordered]@{
        status = "WAITING"
        pressLine = $null
        releaseLine = $null
        actionLine = $null
        completionLine = $null
        unexpectedLines = New-Object System.Collections.Generic.List[string]
        lines = New-Object System.Collections.Generic.List[string]
    }
    $buffer = ""
    $started = Get-Date

    $form = New-Object System.Windows.Forms.Form
    $form.Text = $Title
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(650, 360)
    $form.TopMost = $true
    $form.MinimizeBox = $false
    $form.MaximizeBox = $false
    $form.FormBorderStyle = "FixedDialog"

    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Instruction
    $label.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 12)
    $label.AutoSize = $false
    $label.Location = New-Object System.Drawing.Point(24, 22)
    $label.Size = New-Object System.Drawing.Size(585, 170)

    $status = New-Object System.Windows.Forms.Label
    if ($ExpectedRecordAction) {
        $status.Text = "等待 SW3。请按住约 0.2 秒再松开；固件确认 action=$ExpectedRecordAction 后窗口会自动继续。"
    } else {
        $status.Text = "等待 SW3。请按住约 0.2 秒再松开；检测到按下和松开后窗口会自动关闭。"
    }
    $status.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10)
    $status.AutoSize = $false
    $status.Location = New-Object System.Drawing.Point(24, 210)
    $status.Size = New-Object System.Drawing.Size(585, 48)

    $progress = New-Object System.Windows.Forms.ProgressBar
    $progress.Location = New-Object System.Drawing.Point(24, 276)
    $progress.Size = New-Object System.Drawing.Size(585, 24)
    $progress.Minimum = 0
    $progress.Maximum = $TimeoutSeconds

    $form.Controls.Add($label)
    $form.Controls.Add($status)
    $form.Controls.Add($progress)

    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 100
    $timer.Add_Tick({
        $elapsed = ((Get-Date) - $started).TotalSeconds
        $progress.Value = [Math]::Min($TimeoutSeconds, [Math]::Max(0, [int]$elapsed))
        if ($elapsed -gt $TimeoutSeconds) {
            $state.status = "TIMEOUT"
            $timer.Stop()
            $form.Close()
            return
        }

        try {
            $chunk = $Serial.ReadExisting()
        } catch {
            $state.status = "SERIAL_ERROR: $($_.Exception.Message)"
            $timer.Stop()
            $form.Close()
            return
        }
        if (-not $chunk) {
            return
        }

        Add-Content -LiteralPath $RawLogPath -Value $chunk -NoNewline -Encoding UTF8
        $script:buffer += $chunk
        while ($script:buffer -match "^(?<line>.*?)(\r?\n)(?<rest>[\s\S]*)$") {
            $line = $Matches["line"].Trim()
            $script:buffer = $Matches["rest"]
            if (-not $line) {
                continue
            }
            $state.lines.Add($line)
            if ($ExpectedCompletionPattern -and $line -match $ExpectedCompletionPattern) {
                $state.completionLine = $line
                $status.Text = "$ExpectedCompletionLabel 已确认；请松开 SW3。"
                if ($state.releaseLine -and $state.actionLine) {
                    $state.status = "PASS"
                    $timer.Stop()
                    $form.Close()
                    return
                }
                continue
            }
            if ($line -match "\[button-raw\]\s+SW3\s+active_low=1\b") {
                $state.pressLine = $line
                $state.releaseLine = $null
                $status.Text = "已检测到 SW3 按下；请保持约 0.2 秒，等固件确认后再松开。"
                continue
            }
            if ($line -match "\[button\]\s+SW3\s+pressed\b") {
                if (-not $state.pressLine) {
                    $state.pressLine = $line
                }
                $status.Text = "固件已经识别 SW3；等待录音状态确认。"
                continue
            }
            if ($ExpectedRecordAction -and $line -match "\[record\]\s+sw3\s+action=(?<action>[a-z_]+)\b") {
                $action = $Matches["action"]
                if ($action -eq $ExpectedRecordAction) {
                    if ($line -match "\b(?:ignored|rejected)=") {
                        $state.status = "FIRMWARE_REJECTED: $line"
                        $timer.Stop()
                        $form.Close()
                        return
                    }
                    $state.actionLine = $line
                    if ($ExpectedCompletionPattern) {
                        $status.Text = "固件已确认 action=$ExpectedRecordAction；等待 $ExpectedCompletionLabel。"
                    } else {
                        $status.Text = "固件已确认 action=$ExpectedRecordAction；请松开 SW3。"
                    }
                    if ($state.releaseLine -and (-not $ExpectedCompletionPattern -or $state.completionLine)) {
                        $state.status = "PASS"
                        $timer.Stop()
                        $form.Close()
                        return
                    }
                    continue
                }

                $state.unexpectedLines.Add($line)
                if ($ExpectedRecordAction -eq "start" -and $action -eq "stop") {
                    $status.Text = "检测到旧录音被 SW3 停止；请再按住 SW3 约 0.2 秒开始本次录音。"
                } else {
                    $status.Text = "检测到 action=$action，当前等待 action=$ExpectedRecordAction；请按窗口提示继续。"
                }
                $state.pressLine = $null
                $state.releaseLine = $null
                continue
            }
            if ($line -match "\[button-raw\]\s+SW3\s+active_low=0\b") {
                if ($ExpectedRecordAction -and -not $state.actionLine) {
                    $status.Text = "检测到松开，但固件还没确认 action=$ExpectedRecordAction。请按住 0.2-0.5 秒再松开。"
                    $state.pressLine = $null
                    continue
                }
                $state.releaseLine = $line
                if (-not $ExpectedRecordAction -or ($state.actionLine -and (-not $ExpectedCompletionPattern -or $state.completionLine))) {
                    $state.status = "PASS"
                    $timer.Stop()
                    $form.Close()
                    return
                }
                $status.Text = "已检测到松开；还在等待固件完成确认。"
            }
        }
    })

    $script:buffer = $buffer
    [System.Media.SystemSounds]::Exclamation.Play()
    $timer.Start()
    [void]$form.ShowDialog()
    $timer.Dispose()
    $form.Dispose()

    return $state
}

function Convert-PopupState {
    param($State)

    if ($null -eq $State) {
        return $null
    }

    return [ordered]@{
        status = [string]$State.status
        pressLine = $State.pressLine
        releaseLine = $State.releaseLine
        actionLine = $State.actionLine
        completionLine = $State.completionLine
        unexpectedLines = @($State.unexpectedLines | Select-Object -Last 20)
        lineTail = @($State.lines | Select-Object -Last 40)
    }
}

function Get-TextTail {
    param([string]$Path, [int]$Lines = 80)

    if (-not (Test-Path -LiteralPath $Path)) {
        return @()
    }
    return @(Get-Content -LiteralPath $Path -Tail $Lines)
}

function Write-SyncPopupSummary {
    param(
        [string]$Path,
        [string]$Result,
        [string]$Phase,
        [string]$ErrorMessage,
        [string]$SerialPortName,
        $FirstPopup,
        $SecondPopup,
        [object]$CargoExitCode
    )

    $summary = [ordered]@{
        schema = "companion_type.native_ble_sync_popup.v1"
        generatedAt = (Get-Date).ToUniversalTime().ToString("o")
        result = $Result
        phase = $Phase
        error = $ErrorMessage
        serialPort = $SerialPortName
        recordSeconds = $RecordSeconds
        buttonTimeoutSeconds = $ButtonTimeoutSeconds
        scanTimeoutMs = $ScanTimeoutMs
        notifyTimeoutMs = $NotifyTimeoutMs
        artifacts = [ordered]@{
            cargoLog = "docs/validation/companion-type-native-ble-sync-smoke.log"
            serialLog = "docs/validation/companion-type-native-ble-sync-sw3-serial.log"
            recordingDir = "docs/validation/native-ble-sync-cache"
        }
        popup = [ordered]@{
            start = Convert-PopupState -State $FirstPopup
            stop = Convert-PopupState -State $SecondPopup
        }
        cargo = [ordered]@{
            exitCode = $CargoExitCode
            logTail = Get-TextTail -Path $logPath -Lines 80
        }
        serialTail = Get-TextTail -Path $serialLogPath -Lines 80
    }
    $summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Path -Encoding UTF8
}

$validationDir = Join-Path $RepoRoot "docs\validation"
$cacheDir = Join-Path $validationDir "native-ble-sync-cache"
$logPath = Join-Path $validationDir "companion-type-native-ble-sync-smoke.log"
$serialLogPath = Join-Path $validationDir "companion-type-native-ble-sync-sw3-serial.log"
$summaryPath = Join-Path $validationDir "companion-type-native-ble-sync-popup.json"
New-Item -ItemType Directory -Force -Path $validationDir, $cacheDir | Out-Null
Set-Content -LiteralPath $serialLogPath -Value "" -Encoding UTF8
Set-Content -LiteralPath $logPath -Value "" -Encoding UTF8

$resolvedPort = $null
$serial = $null
$first = $null
$second = $null
$phase = "init"
$result = "FAIL"
$errorMessage = $null
$cargoExitCode = $null
try {
    $phase = "resolve-serial"
    $resolvedPort = Resolve-StLinkPort -Requested $SerialPort
    $phase = "open-serial"
    $serial = Open-SerialPort -PortName $resolvedPort -Baud $BaudRate

    $phase = "wait-start-sw3"
    $first = Wait-Sw3PressReleasePopup `
        -Serial $serial `
        -Title "Companion-Type SW3 开始录音" `
        -Instruction "现在按住开发板 SW3/B3（PD1）约 0.2 秒再松开，用来开始录音。不要只轻点一下。窗口会等待固件打印 action=start 后自动关闭；关闭后请对麦克风说话。" `
        -TimeoutSeconds $ButtonTimeoutSeconds `
        -RawLogPath $serialLogPath `
        -ExpectedRecordAction "start"
    if ($first.status -ne "PASS") {
        throw "SW3 start popup detection failed: $($first.status)"
    }

    Start-Sleep -Milliseconds ([int]($RecordSeconds * 1000))

    $phase = "wait-stop-sw3"
    $second = Wait-Sw3PressReleasePopup `
        -Serial $serial `
        -Title "Companion-Type SW3 停止录音" `
        -Instruction "现在按住同一个 SW3/B3（PD1）约 0.2 秒再松开，用来停止录音。窗口会等待固件打印 action=stop 和 manual_store result=1 后自动开始 BLE 同步。" `
        -TimeoutSeconds $ButtonTimeoutSeconds `
        -RawLogPath $serialLogPath `
        -ExpectedRecordAction "stop" `
        -ExpectedCompletionPattern "\[record\]\s+sw3\s+action=manual_store\s+result=1\b" `
        -ExpectedCompletionLabel "manual_store result=1"
    if ($second.status -ne "PASS") {
        throw "SW3 stop popup detection failed: $($second.status)"
    }
} catch {
    $errorMessage = $_.Exception.Message
} finally {
    if ($serial -and $serial.IsOpen) {
        $serial.Close()
    }
    if ($serial) {
        $serial.Dispose()
    }
}

try {
    if ($errorMessage) {
        if ($null -eq $cargoExitCode) {
            $cargoExitCode = 1
        }
    } else {
        Set-Location $RepoRoot
        $env:COMPANION_TYPE_REAL_BLE_SYNC_ACCEPTANCE = "1"
        $env:COMPANION_TYPE_BLE_SCAN_TIMEOUT_MS = [string]$ScanTimeoutMs
        $env:COMPANION_TYPE_BLE_NOTIFY_TIMEOUT_MS = [string]$NotifyTimeoutMs
        $env:COMPANION_TYPE_RECORDING_DIR = $cacheDir

        Write-Output "sw3_start_press=$($first.pressLine)"
        Write-Output "sw3_start_release=$($first.releaseLine)"
        Write-Output "sw3_start_action=$($first.actionLine)"
        Write-Output "sw3_stop_press=$($second.pressLine)"
        Write-Output "sw3_stop_release=$($second.releaseLine)"
        Write-Output "sw3_stop_action=$($second.actionLine)"
        Write-Output "sw3_stop_completion=$($second.completionLine)"

        $phase = "native-ble-sync"
        & cargo test --manifest-path apps/windows/src-tauri/Cargo.toml --lib real_native_ble_recording_sync_smoke -- --nocapture 2>&1 |
            Tee-Object -FilePath $logPath
        $cargoExitCode = $LASTEXITCODE
        if ($cargoExitCode -eq 0) {
            $result = "PASS"
        } else {
            $errorMessage = "cargo native BLE recording sync smoke exited $cargoExitCode"
        }
    }
} catch {
    $errorMessage = $_.Exception.Message
    if ($null -eq $cargoExitCode) {
        $cargoExitCode = 1
    }
} finally {
    Write-SyncPopupSummary `
        -Path $summaryPath `
        -Result $result `
        -Phase $phase `
        -ErrorMessage $errorMessage `
        -SerialPortName $resolvedPort `
        -FirstPopup $first `
        -SecondPopup $second `
        -CargoExitCode $cargoExitCode
}

if ($result -ne "PASS") {
    Write-Error "Companion-Type popup-guided native BLE sync failed in phase '$phase': $errorMessage"
    exit 1
}
exit 0
