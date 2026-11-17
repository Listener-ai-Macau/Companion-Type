param([int]$DurationSeconds = 3600, [int]$IntervalSeconds = 5)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$began = [DateTime]::UtcNow
do {
    $rows = @()
    $errorText = $null
    try {
        foreach ($zone in @(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop)) {
            $currentC = $null
            $criticalC = $null
            if ($zone.CurrentTemperature -gt 0) { $currentC = [Math]::Round($zone.CurrentTemperature / 10.0 - 273.15, 2) }
            if ($zone.CriticalTripPoint -gt 0) { $criticalC = [Math]::Round($zone.CriticalTripPoint / 10.0 - 273.15, 2) }
            $rows += [pscustomobject]@{ Name=$zone.InstanceName; CurrentRawTenthsKelvin=$zone.CurrentTemperature; Celsius=$currentC; FirmwareCriticalRaw=$zone.CriticalTripPoint; FirmwareCriticalCelsius=$criticalC; PhysicalLocation='Unknown firmware thermal zone; not confirmed as motherboard or CPU package' }
        }
    } catch { $errorText = $_.Exception.Message }
    [pscustomobject]@{ At=(Get-Date).ToString('o'); Zones=$rows; QueryError=$errorText; NoHardwareSettingWrites=$true } | ConvertTo-Json -Depth 4 -Compress
    [Console]::Out.Flush()
    if (([DateTime]::UtcNow - $began).TotalSeconds -ge $DurationSeconds) { break }
    Start-Sleep -Seconds $IntervalSeconds
} while ($true)
