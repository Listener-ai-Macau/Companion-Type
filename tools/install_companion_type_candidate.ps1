param(
    [Parameter(Mandatory=$true)][string]$Msi,
    [Parameter(Mandatory=$true)][string]$BuildReceipt,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$OtaManifest,
    [string]$OtaPayload
)
$ErrorActionPreference = 'Stop'
if ([bool]$OtaManifest -ne [bool]$OtaPayload) { throw 'Supply both OTA paths when this delivery needs OTA validation' }
$typeRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).ProviderPath
$Msi = (Resolve-Path -LiteralPath $Msi).ProviderPath
$out = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $out | Out-Null
$installDir = 'C:\Program Files\Companion Type'
$installedExe = Join-Path $installDir 'companion-type.exe'
function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Quote([string]$Value) {
    if ($Value.Contains('"') -or $Value.Contains("`n") -or $Value.Contains("`r")) { throw 'Invalid installer argument' }
    '"' + $Value + '"'
}
function Installer([string]$Arguments) {
    $start = [Diagnostics.ProcessStartInfo]::new('msiexec.exe', $Arguments)
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
    $process = [Diagnostics.Process]::Start($start)
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while (-not $process.WaitForExit(30000)) {
        Write-Output 'Windows Installer is running.'
        if ($watch.Elapsed.TotalSeconds -gt 240) { throw 'Installer timeout; inspect Windows Installer before retrying' }
    }
    if ($process.ExitCode -notin @(0,3010)) { throw "Installer failed: $($process.ExitCode)" }
}
$build = Get-Content -LiteralPath $BuildReceipt -Raw | ConvertFrom-Json
if (-not $build.source_sha256 -or -not $build.artifact.sha256) { throw 'Missing build identity' }
if ((Hash $Msi) -ne $build.artifact.sha256) { throw 'MSI differs from frozen build' }
foreach ($source in $build.source_sha256.PSObject.Properties) {
    if ((Hash (Join-Path $typeRoot $source.Name)) -ne $source.Value) { throw "Source changed after build: $($source.Name)" }
}
if (Get-Process companion-type -ErrorAction SilentlyContinue) { throw 'Companion Type is running; finish current work before installation' }
$tag = (Hash $Msi).Substring(0,12)
$extractDir = Join-Path $out "payload-$tag"
if (Test-Path -LiteralPath $extractDir) { throw 'Use a fresh extraction directory for this candidate' }
Installer ('/a ' + (Quote $Msi) + ' /qn /norestart TARGETDIR=' + (Quote $extractDir) + ' /L*v ' + (Quote (Join-Path $out "extract-$tag.log")))
$payloadDir = Join-Path $extractDir 'PFiles\Companion Type'
$payloadExe = Join-Path $payloadDir 'companion-type.exe'
$releaseDir = Join-Path $typeRoot 'apps\windows\src-tauri\target\release'
$releaseExe = Join-Path $releaseDir 'companion-type.exe'
$releaseBytes = [IO.File]::ReadAllBytes($releaseExe)
$payloadBytes = [IO.File]::ReadAllBytes($payloadExe)
if ($releaseBytes.Length -ne $payloadBytes.Length) { throw 'Release and MSI EXE lengths differ' }
$patch = [Collections.Generic.List[int]]::new()
for ($i=0; $i -lt $releaseBytes.Length; $i++) { if ($releaseBytes[$i] -ne $payloadBytes[$i]) { $patch.Add($i) } }
if ($patch.Count -gt 16 -or ($patch.Count -gt 0 -and $patch[-1]-$patch[0]+1 -ne $patch.Count)) { throw 'Unexpected MSI executable patch' }
if ((Hash (Join-Path $releaseDir 'companion_type_lib.dll')) -ne (Hash (Join-Path $payloadDir 'companion_type_lib.dll'))) { throw 'Release and MSI DLL differ' }
$registrations = @(Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*','HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -eq 'Companion Type' })
foreach ($registration in $registrations) {
    if ($registration.InstallLocation.TrimEnd('\') -ne $installDir -or $registration.PSChildName -notmatch '^\{[0-9A-Fa-f-]{36}\}$') { throw 'Unexpected product registration' }
    Installer ('/x ' + $registration.PSChildName + ' /qn /norestart /L*v ' + (Quote (Join-Path $out "uninstall-$tag.log")))
}
$installLog = Join-Path $out "install-$tag.log"
Installer ('/i ' + (Quote $Msi) + ' /qn /norestart ADDLOCAL=ALL /L*v ' + (Quote $installLog))
foreach ($name in @('companion-type.exe','companion_type_lib.dll')) {
    if ((Hash (Join-Path $installDir $name)) -ne (Hash (Join-Path $payloadDir $name))) { throw "Installed file differs from MSI: $name" }
}
# Execute the installed program's existing read-only CLI. This never opens a
# browser/window, scans hardware, uploads recordings or changes user settings.
$stdout = Join-Path $out "installed-ota-validation-$tag.log"
$stderr = Join-Path $out "installed-ota-validation-$tag.stderr.log"
if ($OtaManifest -and $OtaPayload) {
$manifestPath = (Resolve-Path -LiteralPath $OtaManifest).ProviderPath
$payloadPath = (Resolve-Path -LiteralPath $OtaPayload).ProviderPath
$validationArguments = '--resource-ota-validate ' + (Quote $manifestPath) + ' ' + (Quote $payloadPath)
$start = [Diagnostics.ProcessStartInfo]::new($installedExe, $validationArguments)
$start.UseShellExecute = $false
$start.CreateNoWindow = $true
$start.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
$start.RedirectStandardOutput = $true
$start.RedirectStandardError = $true
$process = [Diagnostics.Process]::Start($start)
$readOutput = $process.StandardOutput.ReadToEndAsync()
$readError = $process.StandardError.ReadToEndAsync()
if (-not $process.WaitForExit(30000)) { throw 'Installed read-only validation did not finish within 30 seconds' }
$cliExitCode = $process.ExitCode
[IO.File]::WriteAllText($stdout, $readOutput.GetAwaiter().GetResult())
[IO.File]::WriteAllText($stderr, $readError.GetAwaiter().GetResult())
if ($cliExitCode -ne 0) { throw "Installed CLI validation failed: $cliExitCode" }
$line = Get-Content -LiteralPath $stdout | Where-Object { $_.StartsWith('resource_ota_validate_json=') } | Select-Object -Last 1
if (-not $line) { throw 'Installed validation returned no structured result' }
$validation = $line.Substring('resource_ota_validate_json='.Length) | ConvertFrom-Json
if ($validation.status -ne 'PASS' -or $validation.payloadSha256 -ne (Hash $OtaPayload)) { throw 'Installed validation identity failed' }
} else {
    $validation = $null
    $cliExitCode = $null
}
$result = [ordered]@{
    schema='companion.type.product_polish.install.v1'; result=$(if ($validation) { 'PASS_INSTALL_IDENTITY_AND_READ_ONLY_CLI_ONLY' } else { 'PASS_INSTALL_IDENTITY_ONLY' })
    hardwareAcceptance='NOT_RUN'; fullChainAcceptance='NOT_RUN'; visualAcceptance='NOT_RUN_BY_INSTALL_SCRIPT'
    msi=$Msi; msi_sha256=(Hash $Msi); installed_exe=$installedExe; installed_exe_sha256=(Hash $installedExe)
    payload_exe=$payloadExe; payload_exe_sha256=(Hash $payloadExe); installed_payload_match=$true
    release_exe_sha256=(Hash $releaseExe); installed_dll_sha256=(Hash (Join-Path $installDir 'companion_type_lib.dll'))
    tauri_bundle_metadata_patch_bytes=$patch.Count; install_log=$installLog; install_log_sha256=(Hash $installLog)
    installed_cli_validation=$validation; installed_cli_log=$(if ($validation) { $stdout } else { $null }); installed_cli_log_sha256=$(if ($validation) { Hash $stdout } else { $null })
    installed_cli_exit_code=$cliExitCode
    no_device_connection=$true; no_remote_service_calls=$true; gui_startup='NOT_RUN'; source_sha256=$build.source_sha256
    generated_at=[DateTime]::UtcNow.ToString('o')
}
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $out 'result.json') -Encoding utf8
Write-Output $result.result
