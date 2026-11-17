param([Parameter(Mandatory=$true)][string]$OutputDirectory, [int]$DurationSeconds=60)
# Run only after explicit approval to install the prepared signed PawnIO driver.
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
if (-not (Test-Path 'HKLM:/SYSTEM/CurrentControlSet/Services/PawnIO')) { throw 'Prepared sensor driver is not installed; no automatic installation.' }
if ($DurationSeconds -lt 10 -or $DurationSeconds -gt 3600) { throw 'Bounded monitor duration required.' }
$tool='E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/system-restart-20261116-2315/prepared-cpu-sensor-tool/tool'
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Preserve existing temperature evidence.' }
[IO.Directory]::CreateDirectory($OutputDirectory) | Out-Null
[Reflection.Assembly]::LoadFrom(($tool+'/LibreHardwareMonitorLib.dll')) | Out-Null
$computer=New-Object LibreHardwareMonitor.Hardware.Computer
$computer.IsCpuEnabled=$true
$computer.IsMotherboardEnabled=$false
$computer.IsGpuEnabled=$false
$computer.IsMemoryEnabled=$false
$computer.IsStorageEnabled=$false
$computer.IsNetworkEnabled=$false
$computer.IsControllerEnabled=$false
$computer.IsPsuEnabled=$false
$computer.IsBatteryEnabled=$false
$stream=[IO.File]::Open(($OutputDirectory+'/cpu-temperatures.jsonl'),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
$writer=New-Object IO.StreamWriter($stream,(New-Object Text.UTF8Encoding($false)))
$began=[DateTime]::UtcNow
try {
    $computer.Open()
    do {
        $rows=@()
        foreach ($hardware in $computer.Hardware) {
            if ($hardware.HardwareType.ToString() -ne 'Cpu') { throw 'Unexpected non-CPU enumeration.' }
            $hardware.Update()
            foreach ($sensor in $hardware.Sensors) {
                if ($sensor.SensorType.ToString() -eq 'Temperature') {
                    $rows += [pscustomobject]@{ Hardware=$hardware.Name; Name=$sensor.Name; Identifier=$sensor.Identifier.ToString(); Celsius=$sensor.Value }
                }
            }
        }
        $packet=[pscustomobject]@{ At=(Get-Date).ToString('o'); Sensors=$rows; SensorSettingsWritten=$false; MotherboardOrEcProbed=$false }
        $writer.WriteLine(($packet | ConvertTo-Json -Depth 4 -Compress));$writer.Flush();$stream.Flush($true)
        if (([DateTime]::UtcNow-$began).TotalSeconds -ge $DurationSeconds) { break }
        Start-Sleep -Seconds 5
    } while ($true)
} finally { $computer.Close();$writer.Dispose();$stream.Dispose() }
