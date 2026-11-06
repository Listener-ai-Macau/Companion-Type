$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$qaEvents = @()
foreach ($qaLog in @('Microsoft-Windows-TWinUI/Operational','Microsoft-Windows-AppModel-Runtime/Admin','Microsoft-Windows-Shell-Core/Operational')) {
 try {
  $qaRows = Get-WinEvent -FilterHashtable @{LogName=$qaLog;StartTime=(Get-Date).AddMinutes(-30);Level=@(2,3)} -MaxEvents 80 -ErrorAction Stop
  foreach ($qaEvent in $qaRows) {
   if ($qaEvent.Message -match 'Share|分享|共享|Companion|DataTransfer') {
    $qaEvents += [ordered]@{time=$qaEvent.TimeCreated.ToString('o');log=$qaLog;id=$qaEvent.Id;message=$qaEvent.Message}
   }
  }
 } catch { [Console]::WriteLine('No matching enabled event source: '+$qaLog) }
}
$qaJson = ConvertTo-Json -InputObject @($qaEvents) -Depth 6
[IO.File]::WriteAllText('E:\CodexData\Companion\.build-cache\windows-share068\related-system-events.json',$qaJson,(New-Object System.Text.UTF8Encoding($false)))
[Console]::WriteLine($qaJson)
