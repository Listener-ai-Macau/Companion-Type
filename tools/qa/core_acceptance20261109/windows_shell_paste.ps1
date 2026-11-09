param([Parameter(Mandatory=$true)][string]$DestinationPath)
$ErrorActionPreference='Stop'
if($env:GITHUB_ACTIONS -ne 'true'){throw 'Dedicated hosted CI required; no owner desktop fallback.'}
$destination=[System.IO.Path]::GetFullPath($DestinationPath)
if(-not [System.IO.Directory]::Exists($destination)){throw 'Explicit receiver folder is missing.'}
$shell=New-Object -ComObject Shell.Application
$folder=$shell.NameSpace($destination)
if($null -eq $folder){throw 'Windows Shell could not bind the explicit destination.'}
$item=$folder.Self
if(-not [string]::Equals($item.Path.TrimEnd([char]92),$destination.TrimEnd([char]92),[StringComparison]::OrdinalIgnoreCase)){throw 'Shell destination differs from the owned folder.'}
$paste=$null
$names=[System.Collections.Generic.List[string]]::new()
foreach($verb in $item.Verbs()){
 $name=$verb.Name.Replace('&','').Trim()
 $names.Add($name)
 if($name -eq 'Paste' -or $name -eq ([string][char]0x7C98+[char]0x8D34)){
  if($null -ne $paste){throw 'Ambiguous Paste menu command.'}
  $paste=$verb
 }
}
[Console]::WriteLine(($names | ConvertTo-Json -Compress))
if($null -eq $paste){throw 'Windows Shell does not offer Paste for the actual clipboard payload.'}
# This is the native shortcut-menu action, not Copy-Item.
# https://learn.microsoft.com/en-us/windows/win32/shell/folderitem-invokeverb
$paste.DoIt()
[Console]::WriteLine('Native folder Paste command invoked; actual output must still be verified.')
