param([int]$DurationSeconds=3600,[int]$IntervalSeconds=5)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
if (-not (Test-Path 'HKLM:/SYSTEM/CurrentControlSet/Services/PawnIO')) { throw 'Explicitly authorized sensor driver is not installed.' }
$tool='E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/system-restart-20261116-2315/prepared-cpu-sensor-tool/tool'
[Reflection.Assembly]::LoadFrom(($tool+'/LibreHardwareMonitorLib.dll')) | Out-Null
$computer=New-Object LibreHardwareMonitor.Hardware.Computer
$computer.IsCpuEnabled=$true
$computer.IsMotherboardEnabled=$false;$computer.IsGpuEnabled=$false;$computer.IsMemoryEnabled=$false
$computer.IsStorageEnabled=$false;$computer.IsNetworkEnabled=$false;$computer.IsControllerEnabled=$false
$computer.IsPsuEnabled=$false;$computer.IsBatteryEnabled=$false
$began=[DateTime]::UtcNow
try {
    $computer.Open()
    do {
        $sensors=@();$zones=@();$queryErrors=@()
        foreach ($hardware in $computer.Hardware) {
            if ($hardware.HardwareType.ToString() -ne 'Cpu') { throw 'Non-CPU hardware enumeration is not in this profile.' }
            $hardware.Update()
            foreach ($sensor in $hardware.Sensors) {
                if ($sensor.SensorType.ToString() -eq 'Temperature') {
                    $sensors += [pscustomobject]@{ Hardware=$hardware.Name; Name=$sensor.Name; Identifier=$sensor.Identifier.ToString(); Celsius=$sensor.Value }
                }
            }
        }
        try {
            foreach ($zone in @(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop)) {
                $c=$null;$critical=$null
                if ($zone.CurrentTemperature -gt 0) {$c=[Math]::Round($zone.CurrentTemperature/10.0-273.15,2)}
                if ($zone.CriticalTripPoint -gt 0) {$critical=[Math]::Round($zone.CriticalTripPoint/10.0-273.15,2)}
                $zones += [pscustomobject]@{ Name=$zone.InstanceName; CurrentRawTenthsKelvin=$zone.CurrentTemperature; Celsius=$c; FirmwareCriticalCelsius=$critical; PhysicalLocation='Unidentified firmware thermal zone' }
            }
        } catch { $queryErrors += $_.Exception.Message }
        [pscustomobject]@{ At=(Get-Date).ToString('o'); CpuSensors=$sensors; Zones=$zones; QueryErrors=$queryErrors; NoHardwareSettingWrites=$true; ExternalGpuQueried=$false; MotherboardEcOrSmbusProbed=$false } | ConvertTo-Json -Depth 5 -Compress
        [Console]::Out.Flush()
        if (([DateTime]::UtcNow-$began).TotalSeconds -ge $DurationSeconds) { break }
        Start-Sleep -Seconds $IntervalSeconds
    } while ($true)
} finally { $computer.Close() }
