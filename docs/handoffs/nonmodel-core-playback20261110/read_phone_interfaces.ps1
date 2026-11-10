$ErrorActionPreference = 'Stop'
$items = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like '*VID_2717&PID_FF40*' } | ForEach-Object {
    $compatible = @(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_CompatibleIds -ErrorAction SilentlyContinue).Data
    $hardware = @(Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_HardwareIds -ErrorAction SilentlyContinue).Data
    [pscustomobject]@{ Class=$_.Class; Name=$_.FriendlyName; Status=$_.Status; Problem=$_.Problem; HardwareIds=$hardware; CompatibleIds=$compatible }
})
ConvertTo-Json -InputObject $items -Compress -Depth 4
