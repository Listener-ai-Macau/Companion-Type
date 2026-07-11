param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$MsiPath = "",
    [int]$LaunchSeconds = 5,
    [switch]$NoPopup
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Show-InstallNotice {
    param([string]$Message)

    if ($NoPopup) {
        return
    }

    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Companion-Type MSI 安装验证"
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(680, 300)
    $form.TopMost = $true
    $form.MinimizeBox = $false
    $form.MaximizeBox = $false
    $form.FormBorderStyle = "FixedDialog"

    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Message
    $label.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 12)
    $label.AutoSize = $false
    $label.Location = New-Object System.Drawing.Point(24, 24)
    $label.Size = New-Object System.Drawing.Size(620, 145)

    $button = New-Object System.Windows.Forms.Button
    $button.Text = "开始安装验证"
    $button.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10)
    $button.Location = New-Object System.Drawing.Point(245, 195)
    $button.Size = New-Object System.Drawing.Size(170, 38)
    $button.Add_Click({ $form.Close() })

    $form.Controls.Add($label)
    $form.Controls.Add($button)
    [System.Media.SystemSounds]::Exclamation.Play()
    [void]$form.ShowDialog()
    $form.Dispose()
}

function Resolve-LatestMsi {
    param([string]$Root, [string]$Requested)

    if ($Requested.Trim()) {
        $resolved = Resolve-Path -LiteralPath $Requested.Trim()
        return $resolved.Path
    }

    $bundleDir = Join-Path $Root "apps\windows\src-tauri\target\release\bundle\msi"
    $msi = Get-ChildItem -LiteralPath $bundleDir -Filter "*.msi" -ErrorAction Stop |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $msi) {
        throw "No MSI found under $bundleDir"
    }
    return $msi.FullName
}

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-MsiInstall {
    param(
        [string]$Path,
        [string]$LogPath,
        [bool]$Elevated
    )

    $arguments = @(
        "/i",
        "`"$Path`"",
        "/qn",
        "/norestart",
        "/L*v",
        "`"$LogPath`""
    )

    $startInfo = @{
        FilePath = "msiexec.exe"
        ArgumentList = $arguments
        Wait = $true
        PassThru = $true
    }
    if ($Elevated) {
        $startInfo.Verb = "RunAs"
    }

    $process = Start-Process @startInfo
    return [ordered]@{
        elevated = $Elevated
        exitCode = $process.ExitCode
        accepted = @(0, 3010, 1638) -contains $process.ExitCode
    }
}

function Get-RegistryInstallEvidence {
    $roots = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )

    $items = @()
    foreach ($root in $roots) {
        try {
            $properties = @(Get-ItemProperty -Path $root -ErrorAction Stop)
            foreach ($property in $properties) {
                if ($property.DisplayName -notlike "Companion Type*") {
                    continue
                }
                $items += [ordered]@{
                    displayName = $property.DisplayName
                    displayVersion = $property.DisplayVersion
                    installLocation = $property.InstallLocation
                    displayIcon = $property.DisplayIcon
                    uninstallString = $property.UninstallString
                    registryPath = $property.PSPath
                }
            }
        } catch {
            continue
        }
    }
    return @($items)
}

function Convert-DisplayIconPath {
    param([string]$Value)

    if (-not $Value) {
        return $null
    }
    $trimmed = $Value.Trim()
    if ($trimmed.StartsWith('"')) {
        $second = $trimmed.IndexOf('"', 1)
        if ($second -gt 1) {
            return $trimmed.Substring(1, $second - 1)
        }
    }
    return ($trimmed -replace ",\d+$", "")
}

function Find-InstalledExe {
    param(
        [string]$Root,
        [object[]]$RegistryEvidence
    )

    $candidates = @()

    foreach ($entry in $RegistryEvidence) {
        $iconPath = Convert-DisplayIconPath -Value ([string]$entry.displayIcon)
        if ($iconPath -and (Test-Path -LiteralPath $iconPath)) {
            $candidates += [string](Resolve-Path -LiteralPath $iconPath).Path
        }
        if ($entry.installLocation -and (Test-Path -LiteralPath $entry.installLocation)) {
            Get-ChildItem -LiteralPath $entry.installLocation -Filter "*.exe" -File -ErrorAction SilentlyContinue |
                ForEach-Object { $candidates += [string]$_.FullName }
        }
    }

    $programRoots = @()
    foreach ($rootPath in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if ($rootPath) {
            $programRoots += Join-Path $rootPath "Companion Type"
        }
    }
    if ($env:LOCALAPPDATA) {
        $programRoots += Join-Path $env:LOCALAPPDATA "Programs\Companion Type"
        $programRoots += Join-Path $env:LOCALAPPDATA "Companion Type"
    }

    foreach ($programRoot in $programRoots) {
        if (-not (Test-Path -LiteralPath $programRoot)) {
            continue
        }
        Get-ChildItem -LiteralPath $programRoot -Filter "*.exe" -File -Recurse -ErrorAction SilentlyContinue |
            ForEach-Object { $candidates += [string]$_.FullName }
    }

    $repoFull = (Resolve-Path -LiteralPath $Root).Path.TrimEnd("\")
    $repoFullLower = $repoFull.ToLowerInvariant()
    $distinct = @($candidates | Where-Object { $_ } | ForEach-Object { [string]$_ } | Select-Object -Unique)

    foreach ($candidate in $distinct) {
        if (-not (Test-Path -LiteralPath $candidate)) {
            continue
        }
        $candidateLower = $candidate.ToLowerInvariant()
        if ($candidateLower.StartsWith($repoFullLower)) {
            continue
        }
        if ($candidateLower.EndsWith("companion type.exe") -or $candidateLower.EndsWith("companion-type.exe")) {
            return $candidate
        }
    }

    foreach ($candidate in $distinct) {
        if (-not (Test-Path -LiteralPath $candidate)) {
            continue
        }
        $candidateLower = $candidate.ToLowerInvariant()
        if (-not $candidateLower.StartsWith($repoFullLower)) {
            return $candidate
        }
    }

    return $null
}

function Get-TextTail {
    param([string]$Path, [int]$Lines = 80)

    if (-not (Test-Path -LiteralPath $Path)) {
        return @()
    }
    return @(Get-Content -LiteralPath $Path -Tail $Lines)
}

function Stop-LaunchedProcess {
    param([int]$ProcessId)

    if ($ProcessId -le 0) {
        return
    }
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) {
        return
    }
    try {
        [void]$process.CloseMainWindow()
        Start-Sleep -Seconds 2
    } catch {
    }
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
}

$validationDir = Join-Path $RepoRoot "docs\validation"
New-Item -ItemType Directory -Force -Path $validationDir | Out-Null
$summaryPath = Join-Path $validationDir "companion-type-msi-install-smoke.json"
$installLogPath = Join-Path $validationDir "companion-type-msi-install.log"

$result = "FAIL"
$phase = "init"
$errorMessage = $null
$msi = $null
$installAttempt = $null
$elevatedAttempt = $null
$registryEvidence = @()
$installedExe = $null
$launched = $null

try {
    $phase = "resolve-msi"
    $msi = Resolve-LatestMsi -Root $RepoRoot -Requested $MsiPath

    Show-InstallNotice -Message "接下来会真实安装 Companion Type MSI。`r`n`r`n如果 Windows 弹出 UAC 或安装确认，请选择“是/允许”。脚本安装完成后会自动启动安装后的 Companion Type，并把结果写入 docs/validation/companion-type-msi-install-smoke.json。"

    $phase = "msi-install"
    $installAttempt = Invoke-MsiInstall -Path $msi -LogPath $installLogPath -Elevated:$false
    if (-not $installAttempt.accepted -and -not (Test-IsAdmin)) {
        Show-InstallNotice -Message "普通权限安装没有通过。`r`n`r`n下一步会请求管理员权限重新安装 Companion Type；看到 UAC 时请选择“是/允许”。"
        $phase = "msi-install-elevated"
        $elevatedAttempt = Invoke-MsiInstall -Path $msi -LogPath $installLogPath -Elevated:$true
    }

    $acceptedInstall = $installAttempt.accepted -or ($elevatedAttempt -and $elevatedAttempt.accepted)
    $phase = "locate-installed-exe"
    $registryEvidence = Get-RegistryInstallEvidence
    $installedExe = Find-InstalledExe -Root $RepoRoot -RegistryEvidence $registryEvidence
    if (-not $installedExe) {
        throw "Installed Companion Type executable was not found after MSI install"
    }

    if (-not $acceptedInstall) {
        throw "MSI install did not return an accepted exit code"
    }

    $phase = "launch-installed-app"
    $started = Start-Process -FilePath $installedExe -PassThru
    Start-Sleep -Seconds $LaunchSeconds
    $running = Get-Process -Id $started.Id -ErrorAction SilentlyContinue
    $processPath = if ($running) { $running.Path } else { $null }
    $launched = [ordered]@{
        pid = $started.Id
        requestedPath = $installedExe
        processPath = $processPath
        aliveAfterSeconds = [bool]$running
    }
    if (-not $running) {
        throw "Installed Companion Type process exited before launch smoke observation"
    }

    $repoFull = (Resolve-Path -LiteralPath $RepoRoot).Path.TrimEnd("\")
    if ($processPath -and $processPath.ToLowerInvariant().StartsWith($repoFull.ToLowerInvariant())) {
        throw "Launch smoke used repo release executable instead of installed executable: $processPath"
    }

    $result = "PASS"
} catch {
    $errorMessage = $_.Exception.Message
} finally {
    if ($launched -and $launched.pid) {
        Stop-LaunchedProcess -ProcessId ([int]$launched.pid)
    }

    $summary = [ordered]@{
        schema = "companion_type.msi_install_smoke.v1"
        generatedAt = (Get-Date).ToUniversalTime().ToString("o")
        result = $result
        phase = $phase
        error = $errorMessage
        msiPath = $msi
        installLog = $installLogPath
        installAttempt = $installAttempt
        elevatedAttempt = $elevatedAttempt
        registryEvidence = $registryEvidence
        installedExe = $installedExe
        launched = $launched
        installLogTail = Get-TextTail -Path $installLogPath -Lines 80
    }
    $summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
}

if ($result -ne "PASS") {
    Write-Error "Companion-Type MSI install smoke failed in phase '$phase': $errorMessage"
    exit 1
}

Write-Output "PASS Companion-Type MSI install smoke: $summaryPath"
exit 0
