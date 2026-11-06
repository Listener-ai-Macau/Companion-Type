$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$qaRoot = 'C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-device-phone-closure055\phone-followup\unified058\priority12\windows-share068'
$qaBuild = Get-Content -LiteralPath (Join-Path $qaRoot 'build-result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$qaIdentity = 'Denzic.Companion.PublicShareQA068'
if ($qaBuild.identity -ne $qaIdentity) { throw 'Unexpected package identity' }
if ((Get-FileHash -LiteralPath $qaBuild.package -Algorithm SHA256).Hash.ToLowerInvariant() -ne $qaBuild.sha256) { throw 'Package digest mismatch' }
$qaExisting = Get-AppxPackage -Name $qaIdentity
if ($qaExisting) { throw 'Existing package found: preserve it and inspect before replacing' }
# Official Windows11 test deployment. No certificate, developer mode, privacy,
# firewall or other security setting is modified.
Add-AppxPackage -Path $qaBuild.package -AllowUnsigned -ErrorAction Stop
$qaInstalled = Get-AppxPackage -Name $qaIdentity
if (-not $qaInstalled) { throw 'Package deployment was not confirmed' }
$qaActual = Join-Path $qaInstalled.InstallLocation 'ShareReceiver.exe'
if ((Get-FileHash -LiteralPath $qaActual -Algorithm SHA256).Hash.ToLowerInvariant() -ne $qaBuild.exeSha256) { throw 'Installed executable digest mismatch' }
$qaReceipt = [ordered]@{
 state = 'OWN_PUBLIC_SHARE_QA_INSTALLED_NOT_LAUNCHED'
 packageFullName = $qaInstalled.PackageFullName
 packageFamilyName = $qaInstalled.PackageFamilyName
 installLocation = [string]$qaInstalled.InstallLocation
 sourceSha256 = $qaBuild.sha256
 executableMatched = $true
 securitySettingsChanged = $false
 foregroundLaunched = $false
 actualShareReceived = $false
}
$qaJson = $qaReceipt | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText((Join-Path $qaRoot 'installation.json'), $qaJson, (New-Object System.Text.UTF8Encoding($false)))
[Console]::WriteLine($qaJson)
