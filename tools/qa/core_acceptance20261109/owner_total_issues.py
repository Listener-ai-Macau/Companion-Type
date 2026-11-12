"""Individual reports from explicit original-window actions; no product controls."""
from datetime import datetime
import hashlib,json

REPORT='记录问题'

def reported_issues(events,prompt_pid,not_before,version,steps,seen):
    rows=[]
    for line in events.splitlines():
        try:
            event=json.loads(line)
            at=datetime.fromisoformat(event['at'].replace('Z','+00:00')).timestamp()
            context=event.get('context')or{}
            index=context['stepIndex']
        except (ValueError,KeyError,TypeError):
            continue
        if (event.get('event')!='action_button|'+REPORT or event.get('processId')!=prompt_pid
            or at<not_before or context.get('version')!=version or type(index)is not int
            or not 0<=index<len(steps) or context.get('stepTitle')!=steps[index][0]):
            continue
        identity=hashlib.sha256(line.encode('utf8')).hexdigest()
        if identity in seen:continue
        seen.add(identity)
        rows.append(dict(eventId=identity,reportedAt=event['at'],version=version,stepIndex=index,
                         stepTitle=steps[index][0],ownerQuote=str(event.get('text')or'')))
    return rows
