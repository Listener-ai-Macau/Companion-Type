# Engineering-only instrumentation. Never called by the Owner acceptance runner.
# Read the one original source; change only modal hosting on an inaccessible
# station because WinForms ShowDialog rejects noninteractive stations.
$sourcePath = 'C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/scripts/operator_prompt.ps1'
$source = [System.IO.File]::ReadAllText($sourcePath)
$digest = [Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes($source)))
# File hash is separately bound by the launching controller, before spawning.
if (($source.Split('[void]$form.ShowDialog()')).Count -ne 2) { throw 'Unexpected original host boundary' }
$hostRender = @'
$renderTimer = New-Object System.Windows.Forms.Timer
$renderTimer.Interval = 400
$script:lastPreview = ''
$script:lastProbe = ''
$renderTimer.Add_Tick({
    try {
        $previewUpdate = [System.IO.File]::ReadAllText($UpdatePath) | ConvertFrom-Json
        if ($previewUpdate.previewFile -and $previewUpdate.previewFile -ne $script:lastPreview) {
            Set-OperatorPromptLiveUpdate -Update $previewUpdate
            if ($previewUpdate.probeId -and $previewUpdate.probeId -ne $script:lastProbe) {
                if ($null -ne $previewUpdate.PSObject.Properties['probeText']) { $textBox.Text = [string]$previewUpdate.probeText }
                if ($previewUpdate.probeAction) {
                    $probeButton = @($runtimeActionButtons | Where-Object { $_.Text -eq [string]$previewUpdate.probeAction })
                    if ($probeButton.Count -ne 1 -or -not $probeButton[0].Enabled -or -not $probeButton[0].Visible) { throw 'Probe action is not visible and enabled' }
                    $probeButton[0].PerformClick()
                }
                $script:lastProbe = [string]$previewUpdate.probeId
            }
            [System.IO.File]::WriteAllText(([string]$previewUpdate.previewFile + '.json'), ([PSCustomObject]@{text=$textBox.Text;alive=(-not $form.IsDisposed);context=$script:eventContext} | ConvertTo-Json -Depth 4))

            $bitmap = [System.Drawing.Bitmap]::new($form.Width, $form.Height)
            try {
                $form.DrawToBitmap($bitmap, [System.Drawing.Rectangle]::new(0, 0, $form.Width, $form.Height))
                # DrawToBitmap reverses overlapping child-control order. Render
                # the original frontmost panel at its own form coordinates.
                if ($actionPanel -and $previewUpdate.visibleActions.Count -gt 0) {
                    $offset = $form.PointToScreen([System.Drawing.Point]::Empty)
                    $outer = $form.Bounds.Location
                    $actionPanel.DrawToBitmap($bitmap, [System.Drawing.Rectangle]::new(
                        $actionPanel.Left + $offset.X - $outer.X,
                        $actionPanel.Top + $offset.Y - $outer.Y,
                        $actionPanel.Width, $actionPanel.Height))
                }
                $bitmap.Save([string]$previewUpdate.previewFile, [System.Drawing.Imaging.ImageFormat]::Png)
            } finally { $bitmap.Dispose() }
            $script:lastPreview = [string]$previewUpdate.previewFile
        }
    } catch { [System.IO.File]::WriteAllText(($OutputPath + '.render-error'), $_.ToString()) }
})
$renderTimer.Start()
[System.Windows.Forms.Application]::Run($form)
$renderTimer.Stop()
$renderTimer.Dispose()
'@
$source = $source.Replace('[void]$form.ShowDialog()', $hostRender)
$source = $source.Replace('Join-Path $PSScriptRoot "operator_prompt_ui.ps1"', "'C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/scripts/operator_prompt_ui.ps1'")
& ([scriptblock]::Create($source)) @args
