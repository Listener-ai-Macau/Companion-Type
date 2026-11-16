$ErrorActionPreference = 'Stop'
$gpuDevice = Get-PnpDevice -Class Display -PresentOnly | Where-Object FriendlyName -Like '*6800 XT*' | Select-Object -First 1
if (-not $gpuDevice) { throw 'RX6800XT is not present; no GPU initialization attempted.' }
$cursorId = $gpuDevice.InstanceId
$rows = @()
for ($hop = 0; $hop -lt 12 -and $cursorId; $hop++) {
    $deviceNode = Get-PnpDevice -InstanceId $cursorId
    $parentNode = Get-PnpDeviceProperty -InstanceId $cursorId -KeyName DEVPKEY_Device_Parent -ErrorAction SilentlyContinue
    $locationNode = Get-PnpDeviceProperty -InstanceId $cursorId -KeyName DEVPKEY_Device_LocationPaths -ErrorAction SilentlyContinue
    $rows += [pscustomobject]@{ Hop=$hop; Name=$deviceNode.FriendlyName; Class=$deviceNode.Class; Status=$deviceNode.Status; InstanceId=$cursorId; LocationPaths=$locationNode.Data }
    $cursorId = $parentNode.Data
}
$report = [pscustomobject]@{ At=(Get-Date).ToString('o'); ReadOnly=$true; NeuralRuntimeLoaded=$false; DeviceSettingsChanged=$false; Parents=$rows }
$target = 'E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/system-restart-20261116-2315/egpu-topology.json'
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $target -Encoding UTF8
$rows | Select-Object Hop,Name,Class,Status | ConvertTo-Json -Compress
