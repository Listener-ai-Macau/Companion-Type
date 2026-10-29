param(
    [Parameter(Mandatory=$true)][string]$Msi,
    [Parameter(Mandatory=$true)][string]$BuildReceipt,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$ReleaseDirectory,
    [string]$OtaManifest,
    [string]$OtaPayload,
    [string]$SourceCommit,
    [string]$ExpectedInstalledExeSha256,
    [string]$CheckpointPython = 'python'
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
function AssertInstallBaseline {
    if (Get-Process companion-type -ErrorAction SilentlyContinue) { throw 'Companion Type is running; finish current work before installation' }
    if ($SourceCommit -and ((-not (Test-Path -LiteralPath $installedExe)) -or (Hash $installedExe) -ne $ExpectedInstalledExeSha256)) {
        throw 'Installed Type changed from the explicitly pinned baseline; do not replace a newer delivery'
    }
}
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
if ([bool]$SourceCommit -ne [bool]$ExpectedInstalledExeSha256) { throw 'Immutable source mode requires both source commit and exact installed baseline' }
$sourceVerification = $null
if ($SourceCommit) {
    if ($SourceCommit -cnotmatch '^[0-9a-f]{40}$' -or $ExpectedInstalledExeSha256 -cnotmatch '^[0-9a-f]{64}$' -or $build.sourceCommit -ne $SourceCommit) { throw 'Invalid immutable source or installed baseline identity' }
    AssertInstallBaseline
    $sourceProof = Join-Path $out 'source-checkpoint-proof.json'
    & $CheckpointPython (Join-Path $typeRoot 'tools/verify_type_source_checkpoint.py') --repo $typeRoot --receipt $BuildReceipt --commit $SourceCommit --output $sourceProof
    if ($LASTEXITCODE -ne 0) { throw 'Immutable build source verification failed' }
    $sourceVerification = Get-Content -LiteralPath $sourceProof -Raw | ConvertFrom-Json
    if ($sourceVerification.result -ne 'ALL_BUILD_INPUTS_MATCH_IMMUTABLE_GIT' -or $sourceVerification.sourceCommit -ne $SourceCommit) { throw 'Missing immutable build source proof' }
} else {
    foreach ($source in $build.source_sha256.PSObject.Properties) {
        if ((Hash (Join-Path $typeRoot $source.Name)) -ne $source.Value) { throw "Source changed after build: $($source.Name)" }
    }
}
AssertInstallBaseline
$tag = (Hash $Msi).Substring(0,12)
$extractDir = Join-Path $out "payload-$tag"
# MSI administrative extraction does not accept the long content-addressed
# licence paths that fit in normal file APIs. Keep logs at the requested output
# and stage the payload independently when the base path consumes the budget.
if ($extractDir.Length -gt 120) {
    $stageRoot = Join-Path ([IO.Path]::GetTempPath()) 'companion-type-msi'
    $extractDir = Join-Path $stageRoot ($tag + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
    if ($extractDir.Length -gt 120) { throw 'A shorter temporary directory is required for MSI payload extraction' }
    New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
}
if (Test-Path -LiteralPath $extractDir) { throw 'Use a fresh extraction directory for this candidate' }
Installer ('/a ' + (Quote $Msi) + ' /qn /norestart TARGETDIR=' + (Quote $extractDir) + ' /L*v ' + (Quote (Join-Path $out "extract-$tag.log")))
$payloadDir = Join-Path $extractDir 'PFiles\Companion Type'
$payloadExe = Join-Path $payloadDir 'companion-type.exe'
$releaseDir = if ($ReleaseDirectory) {
    (Resolve-Path -LiteralPath $ReleaseDirectory).ProviderPath
} else { Join-Path $typeRoot 'apps\windows\src-tauri\target\release' }
$releaseExe = Join-Path $releaseDir 'companion-type.exe'
$releaseBytes = [IO.File]::ReadAllBytes($releaseExe)
$payloadBytes = [IO.File]::ReadAllBytes($payloadExe)
if ($releaseBytes.Length -ne $payloadBytes.Length) { throw 'Release and MSI EXE lengths differ' }
$patch = [Collections.Generic.List[int]]::new()
for ($i=0; $i -lt $releaseBytes.Length; $i++) { if ($releaseBytes[$i] -ne $payloadBytes[$i]) { $patch.Add($i) } }
if ($patch.Count -gt 16 -or ($patch.Count -gt 0 -and $patch[-1]-$patch[0]+1 -ne $patch.Count)) { throw 'Unexpected MSI executable patch' }
if ((Hash (Join-Path $releaseDir 'companion_type_lib.dll')) -ne (Hash (Join-Path $payloadDir 'companion_type_lib.dll'))) { throw 'Release and MSI DLL differ' }
$registrations = @(Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*','HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -eq 'Companion Type' })
AssertInstallBaseline
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
    release_payload_directory=$releaseDir
    tauri_bundle_metadata_patch_bytes=$patch.Count; install_log=$installLog; install_log_sha256=(Hash $installLog)
    installed_cli_validation=$validation; installed_cli_log=$(if ($validation) { $stdout } else { $null }); installed_cli_log_sha256=$(if ($validation) { Hash $stdout } else { $null })
    installed_cli_exit_code=$cliExitCode
    no_device_connection=$true; no_remote_service_calls=$true; gui_startup='NOT_RUN'; source_sha256=$build.source_sha256
    source_verification=$sourceVerification; expected_installed_exe_sha256=$ExpectedInstalledExeSha256
    generated_at=[DateTime]::UtcNow.ToString('o')
}
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $out 'result.json') -Encoding utf8
Write-Output $result.result
