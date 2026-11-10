$ErrorActionPreference = 'Stop'
$promptPath = 'C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/scripts/operator_prompt.ps1'
# Invocation compatibility only: use the exact shared no-activate form class on
# Windows PowerShell/.NET Framework, whose WinForms has no separate Primitives DLL.
Add-Type -AssemblyName System.Windows.Forms
$source = [System.IO.File]::ReadAllText($promptPath)
$typeSource = [regex]::Match($source, "Add-Type -TypeDefinition @'\r?\n([\s\S]*?)\r?\n'@ -ReferencedAssemblies").Groups[1].Value
if (-not $typeSource.Contains('class ListenerNoActivateEditablePromptFormV2')) { throw 'Original shared no-activate class not found' }
if (-not ('ListenerNoActivateEditablePromptFormV2' -as [type])) {
    Add-Type -TypeDefinition $typeSource -ReferencedAssemblies @([System.Windows.Forms.Form].Assembly.Location, [System.ComponentModel.Component].Assembly.Location)
}
& $promptPath -Title 'Companion 手机调试连接' -ScopeText '手机已连线，缺少调试接口' -Message 'Windows 已识别到小米 13 Ultra 的文件传输，但当前没有 ADB 调试接口。请在手机的开发者选项中打开 USB 调试；如已打开，可关开一次。如出现“允许 USB 调试”，请允许这台电脑。处理后点“已开启”。这不会删除资料，也不需要提供密码或密钥。' -Buttons '已开启,开着但没有授权提示,稍后处理' -NoActivate -TimeoutSeconds 300 -Json -OutputPath 'C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261110-nonmodel-core-playback/phone-debug-response.txt'
