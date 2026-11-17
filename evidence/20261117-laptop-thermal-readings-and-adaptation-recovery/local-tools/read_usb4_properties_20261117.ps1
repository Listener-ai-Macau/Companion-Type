$ErrorActionPreference = 'Stop'
$nodes = Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VEN_1002&DEV_73BF|VEN_1B21&DEV_2463' -or $_.FriendlyName -match 'USB4|Thunderbolt' }
$rows = @()
foreach ($node in $nodes) {
    $props = @{}
    foreach ($key in @('DEVPKEY_Device_DriverVersion','DEVPKEY_Device_DriverDate','DEVPKEY_Device_DriverProvider','DEVPKEY_Device_DriverInfPath','DEVPKEY_Device_InstallDate','DEVPKEY_Device_FirstInstallDate','DEVPKEY_Device_LastArrivalDate','DEVPKEY_Device_LastRemovalDate')) {
        $p = Get-PnpDeviceProperty -InstanceId $node.InstanceId -KeyName $key -ErrorAction SilentlyContinue
        if ($p) {
            $value = $p.Data
            if ($value -is [DateTime]) { $value = $value.ToString('o') }
            $props[$key] = $value
        }
    }
    $rows += [pscustomobject]@{ Name=$node.FriendlyName; InstanceId=$node.InstanceId; Class=$node.Class; Status=$node.Status; Properties=$props }
}
[pscustomobject]@{ At=(Get-Date).ToString('o'); ReadOnly=$true; DeviceSettingsChanged=$false; Nodes=$rows } | ConvertTo-Json -Depth 7 -Compress
