param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$InstalledExe = "C:\Program Files\Companion Type\companion-type.exe",
    [int]$WindowLeft = 20,
    [int]$WindowTop = 20,
    [int]$WindowWidth = 1900,
    [int]$WindowHeight = 1380,
    [int]$ScanWaitSeconds = 12,
    [int]$ConnectWaitSeconds = 8,
    [int]$SyncWaitSeconds = 75,
    [int]$SettledWaitSeconds = 5,
    [int]$PopupAutoContinueSeconds = 15,
    [switch]$NoPopup
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class CompanionTypeUiWin32 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out CompanionTypeUiRect rect);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extraInfo);
  public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
  public static readonly IntPtr HWND_NOTOPMOST = new IntPtr(-2);
  public const int SW_RESTORE = 9;
  public const uint SWP_NOMOVE = 0x0002;
  public const uint SWP_NOSIZE = 0x0001;
  public const uint SWP_SHOWWINDOW = 0x0040;
  public const uint LEFTDOWN = 0x0002;
  public const uint LEFTUP = 0x0004;
}
public struct CompanionTypeUiRect { public int Left; public int Top; public int Right; public int Bottom; }
"@

$script:CompanionWindowHandle = [IntPtr]::Zero
$script:CompanionWindowBounds = $null

function Close-InterferingSystemDialogs {
    Get-Process -Name "SystemSettings", "SystemSettingsAdminFlows" -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
}

function Focus-CompanionWindow {
    if ($script:CompanionWindowHandle -eq [IntPtr]::Zero) {
        return
    }

    [void][CompanionTypeUiWin32]::ShowWindow($script:CompanionWindowHandle, [CompanionTypeUiWin32]::SW_RESTORE)
    [void][CompanionTypeUiWin32]::MoveWindow($script:CompanionWindowHandle, $WindowLeft, $WindowTop, $WindowWidth, $WindowHeight, $true)
    [void][CompanionTypeUiWin32]::SetWindowPos(
        $script:CompanionWindowHandle,
        [CompanionTypeUiWin32]::HWND_TOPMOST,
        0,
        0,
        0,
        0,
        [CompanionTypeUiWin32]::SWP_NOMOVE -bor [CompanionTypeUiWin32]::SWP_NOSIZE -bor [CompanionTypeUiWin32]::SWP_SHOWWINDOW
    )
    [void][CompanionTypeUiWin32]::SetForegroundWindow($script:CompanionWindowHandle)
    Start-Sleep -Milliseconds 200
}

function Show-Notice {
    param([string]$Message)

    if ($NoPopup) {
        return
    }

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Companion-Type 安装版 UI 同步验证"
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(720, 300)
    $form.TopMost = $true
    $form.MinimizeBox = $false
    $form.MaximizeBox = $false
    $form.FormBorderStyle = "FixedDialog"

    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Message
    $label.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 12)
    $label.AutoSize = $false
    $label.Location = New-Object System.Drawing.Point(24, 24)
    $label.Size = New-Object System.Drawing.Size(660, 145)

    $button = New-Object System.Windows.Forms.Button
    $button.Text = "开始"
    $button.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10)
    $button.Location = New-Object System.Drawing.Point(300, 195)
    $button.Size = New-Object System.Drawing.Size(120, 38)
    $button.Add_Click({ $form.Close() })

    $form.Controls.Add($label)
    $form.Controls.Add($button)
    $timer = $null
    if ($PopupAutoContinueSeconds -gt 0) {
        $timer = New-Object System.Windows.Forms.Timer
        $timer.Interval = $PopupAutoContinueSeconds * 1000
        $timer.Add_Tick({
            $timer.Stop()
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
        $form.Dispose()
    }
}

function Get-AppWindowRect {
    param($Process)

    $handle = $script:CompanionWindowHandle
    for ($index = 0; $index -lt 20; $index++) {
        $Process.Refresh()
        if ($handle -ne [IntPtr]::Zero) {
            break
        }
        if ($Process.MainWindowHandle -ne 0) {
            $handle = $Process.MainWindowHandle
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if ($handle -eq [IntPtr]::Zero) {
        throw "Companion Type main window handle is unavailable"
    }
    $rect = [CompanionTypeUiRect]::new()
    if (-not [CompanionTypeUiWin32]::GetWindowRect($handle, [ref]$rect)) {
        throw "GetWindowRect failed for Companion Type"
    }
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -lt 200 -or $height -lt 200) {
        throw "Companion Type window bounds are too small: ${width}x${height}"
    }
    $bounds = [ordered]@{
        left = $rect.Left
        top = $rect.Top
        right = $rect.Right
        bottom = $rect.Bottom
        width = $width
        height = $height
    }
    $script:CompanionWindowBounds = $bounds
    return $bounds
}

function Try-GetAppWindowRect {
    param($Process)

    try {
        $Process.Refresh()
        if ($Process.MainWindowHandle -eq 0) {
            return $null
        }
        $rect = [CompanionTypeUiRect]::new()
        if (-not [CompanionTypeUiWin32]::GetWindowRect($Process.MainWindowHandle, [ref]$rect)) {
            return $null
        }
        $width = $rect.Right - $rect.Left
        $height = $rect.Bottom - $rect.Top
        return [ordered]@{
            left = $rect.Left
            top = $rect.Top
            right = $rect.Right
            bottom = $rect.Bottom
            width = $width
            height = $height
            area = $width * $height
        }
    } catch {
        return $null
    }
}

function Find-VisibleCompanionProcess {
    $candidates = @()
    foreach ($candidate in @(Get-Process -Name "companion-type" -ErrorAction SilentlyContinue)) {
        $bounds = Try-GetAppWindowRect -Process $candidate
        if (-not $bounds) {
            continue
        }
        if ($bounds.width -lt 500 -or $bounds.height -lt 500) {
            continue
        }
        $candidates += [pscustomobject]@{
            process = $candidate
            bounds = $bounds
            area = $bounds.area
        }
    }
    return @($candidates | Sort-Object area -Descending | Select-Object -First 1)[0]
}

function Save-WindowScreenshot {
    param(
        $Process,
        [string]$Path
    )

    Close-InterferingSystemDialogs
    Focus-CompanionWindow
    $bounds = Get-AppWindowRect -Process $Process
    $width = [Math]::Max(1, [int]$bounds.width)
    $height = [Math]::Max(1, [int]$bounds.height)
    $bitmap = New-Object System.Drawing.Bitmap($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen([int]$bounds.left, [int]$bounds.top, 0, 0, [System.Drawing.Size]::new($width, $height))
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
    return [ordered]@{
        path = $Path
        exists = Test-Path -LiteralPath $Path
        bytes = if (Test-Path -LiteralPath $Path) { (Get-Item -LiteralPath $Path).Length } else { 0 }
        window = $bounds
    }
}

function Convert-ScreenshotSummary {
    param($Screenshot)

    if (-not $Screenshot) {
        return $null
    }
    return [pscustomobject]@{
        path = [string]$Screenshot.path
        exists = [bool]$Screenshot.exists
        bytes = [int64]$Screenshot.bytes
    }
}

function Invoke-ClickRelative {
    param(
        $Process,
        [int]$X,
        [int]$Y
    )

    Close-InterferingSystemDialogs
    Focus-CompanionWindow
    $bounds = Get-AppWindowRect -Process $Process
    $screenX = [int]$bounds.left + $X
    $screenY = [int]$bounds.top + $Y
    [void][CompanionTypeUiWin32]::SetCursorPos($screenX, $screenY)
    Start-Sleep -Milliseconds 100
    [CompanionTypeUiWin32]::mouse_event([CompanionTypeUiWin32]::LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 80
    [CompanionTypeUiWin32]::mouse_event([CompanionTypeUiWin32]::LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
    return [ordered]@{
        relative = [ordered]@{ x = $X; y = $Y }
        screen = [ordered]@{ x = $screenX; y = $screenY }
    }
}

function Start-InstalledApp {
    if (-not (Test-Path -LiteralPath $InstalledExe)) {
        throw "Installed Companion Type executable not found: $InstalledExe"
    }

    Get-Process -Name "companion-type" -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue

    [void](Start-Process -FilePath $InstalledExe -PassThru)
    $visible = $null
    for ($index = 0; $index -lt 80; $index++) {
        Start-Sleep -Milliseconds 250
        $visible = Find-VisibleCompanionProcess
        if ($visible) {
            break
        }
    }
    if (-not $visible) {
        throw "Companion Type installed app main window did not appear"
    }
    $process = $visible.process
    $script:CompanionWindowHandle = $process.MainWindowHandle
    Focus-CompanionWindow
    Start-Sleep -Seconds 2
    $script:CompanionWindowBounds = Get-AppWindowRect -Process $process
    return $process
}

$validationDir = Join-Path $RepoRoot "docs\validation"
New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
$summaryPath = Join-Path $validationDir "companion-type-installed-ui-sync.json"
$result = "FAIL"
$phase = "init"
$errorMessage = $null
$process = $null
$processInfo = $null
$screenshots = [ordered]@{}
$actions = New-Object System.Collections.Generic.List[object]

try {
    Close-InterferingSystemDialogs
    Show-Notice -Message "接下来会启动安装版 Companion Type，并自动点击 Scan、Sync。`r`n`r`n请不要移动 Companion Type 窗口或鼠标。脚本会截图并写入 docs/validation/companion-type-installed-ui-sync.json。"
    $phase = "launch-installed-app"
    Write-Output "phase=$phase"
    $process = Start-InstalledApp
    $processInfo = [ordered]@{
        pid = $process.Id
        path = $process.Path
        window = Get-AppWindowRect -Process $process
    }
    $screenshots["initial"] = Save-WindowScreenshot -Process $process -Path (Join-Path $validationDir "companion-type-installed-ui-sync-00-initial.png")

    $phase = "click-scan"
    Write-Output "phase=$phase"
    $actions.Add([ordered]@{ action = "Scan"; click = Invoke-ClickRelative -Process $process -X 148 -Y 1108 })
    Start-Sleep -Seconds $ScanWaitSeconds
    Close-InterferingSystemDialogs
    $screenshots["afterScan"] = Save-WindowScreenshot -Process $process -Path (Join-Path $validationDir "companion-type-installed-ui-sync-02-after-scan.png")

    $phase = "click-sync"
    Write-Output "phase=$phase"
    $actions.Add([ordered]@{ action = "Sync"; click = Invoke-ClickRelative -Process $process -X 148 -Y 1199 })
    Start-Sleep -Seconds $SyncWaitSeconds
    Close-InterferingSystemDialogs
    $screenshots["afterSync"] = Save-WindowScreenshot -Process $process -Path (Join-Path $validationDir "companion-type-installed-ui-sync-04-after-sync.png")
    if ($SettledWaitSeconds -gt 0) {
        Start-Sleep -Seconds $SettledWaitSeconds
        Close-InterferingSystemDialogs
        $screenshots["afterSyncSettled"] = Save-WindowScreenshot -Process $process -Path (Join-Path $validationDir "companion-type-installed-ui-sync-05-after-sync-settled.png")
    }

    $result = "PASS_SCREENSHOTS_CAPTURED_FOR_VISUAL_REVIEW"
} catch {
    $errorMessage = $_.Exception.Message
} finally {
    $summary = [pscustomobject]@{
        schema = "companion_type.installed_ui_sync.v1"
        generatedAt = (Get-Date).ToUniversalTime().ToString("o")
        result = $result
        phase = $phase
        error = $errorMessage
        installedExe = $InstalledExe
        processId = if ($process) { [int]$process.Id } else { $null }
        processPath = if ($process) { [string]$process.Path } else { $null }
        clickCoordinates = [pscustomobject]@{
            scan = [pscustomobject]@{ x = 148; y = 1108 }
            sync = [pscustomobject]@{ x = 148; y = 1199 }
        }
        actions = @("Scan", "Sync")
        screenshots = [pscustomobject]@{
            initial = Convert-ScreenshotSummary -Screenshot $screenshots["initial"]
            afterScan = Convert-ScreenshotSummary -Screenshot $screenshots["afterScan"]
            afterSync = Convert-ScreenshotSummary -Screenshot $screenshots["afterSync"]
            afterSyncSettled = Convert-ScreenshotSummary -Screenshot $screenshots["afterSyncSettled"]
        }
        visualReview = $null
        note = "Coordinates are relative to a 1900x1380 installed Companion Type window. PASS requires visual review of the post-Sync or settled screenshot."
    }
    $summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
}

if ($result -like "FAIL*") {
    Write-Error "Companion-Type installed app UI sync click chain failed in phase '$phase': $errorMessage"
    exit 1
}

Write-Output "PASS Companion-Type installed app UI sync screenshots captured: $summaryPath"
exit 0
