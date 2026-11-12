from pathlib import Path
from datetime import datetime
import hashlib,json,difflib
P=Path('C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/scripts/operator_prompt.ps1');out=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/step-issue-reporting-r1');out.mkdir(exist_ok=False);raw=P.read_bytes();s=raw.decode('utf-8-sig').replace('\r\n','\n');before=s
(out/'operator_prompt-before.ps1').write_bytes(raw)
old='$script:reviewAllowed = -not $RequireReviewAllowed';assert s.count(old)==1;s=s.replace(old,old+'\n$script:lastInputAcknowledgment = ""\n$script:eventContext = $null')
old='        text = $script:text';assert s.count(old)==1;s=s.replace(old,old+'\n        context = $script:eventContext')
old='            Write-OperatorPromptEvent -Event ("action_button|" + $this.Text)';assert s.count(old)==1;s=s.replace(old,'            if ($null -ne $textBox) { $script:text = $textBox.Text }\n'+old)
old='    # A live controller may observe completion itself.';assert s.count(old)==1
addition='''    # Optional context and acknowledgment for separate per-step reports.
    if ($null -ne $Update.PSObject.Properties['eventContext']) {
        $script:eventContext = $Update.eventContext
    }
    if ($null -ne $Update.PSObject.Properties['observationLabel'] -and $null -ne $observationLabelControl) {
        $observationLabelControl.Text = [string]$Update.observationLabel
    }
    $ack = $Update.inputAcknowledgment
    if ($null -ne $ack -and -not [string]::IsNullOrWhiteSpace([string]$ack.id) -and [string]$ack.id -ne $script:lastInputAcknowledgment) {
        if ($null -ne $textBox -and $textBox.Text -ceq [string]$ack.text) {
            $textBox.Clear()
            $script:text = ""
        }
        $script:lastInputAcknowledgment = [string]$ack.id
    }
'''
s=s.replace(old,addition+old);assert P.read_bytes()==raw;P.write_bytes(s.replace('\n','\r\n').encode('utf8'));(out/'operator_prompt-after.ps1').write_bytes(P.read_bytes())
patch=''.join(difflib.unified_diff(before.splitlines(True),s.splitlines(True),fromfile='operator_prompt.before.ps1',tofile='operator_prompt.ps1'))
B=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261112-product-closure/windows114/step-issue-reporting');B.mkdir(exist_ok=False);(B/'shared-optional-extension.patch').write_text(patch,encoding='utf8');record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),sharedSource=str(P),beforeSha256=hashlib.sha256(raw).hexdigest(),afterSha256=hashlib.sha256(P.read_bytes()).hexdigest(),privateBeforeAndAfter=str(out),scope='Optional original-window action input/context capture and exact-text acknowledgment only. Existing layout/cue/activation/modal path unchanged; no whole shared WIP commit.',ownerDesktopControlled=False,productRecompiled=False)
(B/'shared-source-change.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
