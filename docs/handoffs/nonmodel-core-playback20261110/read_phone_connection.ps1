$ErrorActionPreference = 'Stop'
$phoneDevices = @(Get-PnpDevice -PresentOnly | Where-Object {
    $_.FriendlyName -match 'Android|ADB|Xiaomi|2304|25060|MTP|Redmi|手机' -or $_.Class -eq 'WPD'
} | ForEach-Object {
    $usbIdentity = [regex]::Match($_.InstanceId, 'VID_[0-9A-F]+&PID_[0-9A-F]+', 'IgnoreCase').Value
    [pscustomobject]@{ Class = $_.Class; Name = $_.FriendlyName; Status = $_.Status; Problem = $_.Problem; UsbIdentity = $usbIdentity }
})
ConvertTo-Json -InputObject $phoneDevices -Compress
