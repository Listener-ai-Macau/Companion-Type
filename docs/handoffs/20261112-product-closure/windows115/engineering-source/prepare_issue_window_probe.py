from pathlib import Path
W=Path(__file__).parent
t=(W/'guide_private_render.ps1').read_text(encoding='utf8')
t=t.replace("$script:lastPreview = ''","$script:lastPreview = ''\n$script:lastProbe = ''")
needle='            Set-OperatorPromptLiveUpdate -Update $previewUpdate'
insert='''
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
'''
assert t.count(needle)==1;t=t.replace(needle,needle+insert);(W/'guide_issue_private_render.ps1').write_text(t,encoding='utf8')
t=(W/'preview_guidance112.py').read_text(encoding='utf8').replace('from owner_total_guide import STEPS,NEXT,BACK,native_multiline','from owner_total_guide import STEPS,NEXT,BACK,native_multiline\nfrom owner_total_issues import REPORT')
t=t.replace("R/'docs/handoffs/20261112-product-closure/ui-usability/guide-native-preview-r7'","R/'docs/handoffs/20261112-product-closure/windows114/step-issue-reporting/native-preview-r1'")
t=t.replace("assert sha(shared)=='94978d25097aaa3ecb882a8ec438aa1391eec47cd7bdd761ce783cdd2cab4733'","expected_shared=sha(shared)")
t=t.replace('def show(progress,message,actions,reviews,preview=None):','def show(progress,message,actions,reviews,preview=None,**extra):')
t=t.replace('previewFile=str(preview) if preview else None),ensure_ascii=False)','previewFile=str(preview) if preview else None,**extra),ensure_ascii=False)')
t=t.replace("guide_private_render.ps1","guide_issue_private_render.ps1").replace("'开始,上一步,下一步'","'开始,上一步,记录问题,下一步'").replace("'通过,遇到问题,稍后'","'通过,结束本轮,稍后'")
start=t.index('  frames=[');end=t.index('  for key,progress,message,actions,reviews in frames:',start)
t=t[:start]+"  frames=[('ready','等待开始','准备好后开始。',['开始'],['结束本轮','稍后']),('report','2/8 · '+STEPS[1][0],STEPS[1][1],[BACK,REPORT,NEXT],['结束本轮','稍后']),('final','8/8 · '+STEPS[-1][0],STEPS[-1][1],[BACK,REPORT],['通过','结束本轮','稍后'])]\n"+t[end:]
t=t.replace("image=O/(key+'.png');show(progress,message,actions,reviews,image)","image=O/(key+'.png');extra=dict(eventContext=dict(version='0.1.115',stepIndex=1,stepTitle=STEPS[1][0]));extra.update(dict(probeId='report-one',probeText='公开问题A：按钮不清楚',probeAction=REPORT)if key=='report'else{});show(progress,message,actions,reviews,image,**extra)")
needle="  record['state']='ORIGINAL_GUIDE_CURRENT_STEP_VISIBILITY_AND_PRIVATE_MODELESS_RENDERING_PASSED'"
insert="""  report_events=[json.loads(line)for line in (O/'events.jsonl').read_text(encoding='utf-8-sig').splitlines()if json.loads(line).get('event')=='action_button|'+REPORT]
  assert len(report_events)==1 and report_events[0]['text']=='公开问题A：按钮不清楚' and report_events[0]['context']['stepIndex']==1
  for key,extra,expected in [('ack',dict(inputAcknowledgment=dict(id='saved-one',text='公开问题A：按钮不清楚')),''),('new-draft',dict(probeId='new-draft',probeText='下一条输入'),'下一条输入'),('old-ack',dict(inputAcknowledgment=dict(id='saved-two',text='已经过期的旧输入')),'下一条输入')]:
   target=O/(key+'.png');show('逐条记录探针',STEPS[1][1],[BACK,REPORT,NEXT],['结束本轮','稍后'],target,eventContext=dict(version='0.1.115',stepIndex=1,stepTitle=STEPS[1][0]),**extra)
   deadline=time.monotonic()+8
   while not target.exists()and time.monotonic()<deadline:time.sleep(.2)
   assert target.exists();probe=json.loads(Path(str(target)+'.json').read_text(encoding='utf8'));assert probe['alive']and probe['text']==expected,(key,probe)
  record.update(state='ORIGINAL_STEP_REPORT_ACTION_AND_EXACT_ACK_PRIVATE_RENDERING_PASSED',separateReportActionKeptOriginalWindowAlive=True,exactReportedTextAndStepCaptured=True,ackClearedOnlyExactSubmittedText=True,newDraftPreservedAgainstOldAck=True,actualOwnerModalRuntimeNewlyProved=False)
"""
assert t.count(needle)==1;t=t.replace(needle,insert);t=t.replace("p=spawn(args,env,O,","assert sha(shared)==expected_shared\n  p=spawn(args,env,O,")
(W/'preview_issue_window115.py').write_text(t,encoding='utf8');print('Prepared private original-window issue-report probe; no Owner app or device opened.')
