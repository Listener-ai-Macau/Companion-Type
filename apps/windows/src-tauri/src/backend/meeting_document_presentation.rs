// Older saved minutes contain an English machine-generated header. Translate
// only the complete, recognizable template in the exported presentation;
// never rewrite the saved markdown or headings outside that template.
pub(crate) fn readable_lines(title:&str,content:&str)->Vec<String> {
    let lines=content.lines().collect::<Vec<_>>();
    let marker=format!("# {title}");
    let Some(start)=(0..lines.len().saturating_sub(7)).find(|&i|
        lines[i]==marker && lines[i+1].is_empty() && lines[i+2].starts_with("Generated: ")
        && lines[i+3].starts_with("Duration: ") && lines[i+4].starts_with("Source: ")
        && lines[i+5].starts_with("Minutes engine: ") && lines[i+6].is_empty()
        && lines[i+7]=="## Summary") else {return lines.into_iter().map(str::to_owned).collect()};
    let headings=["## Summary","## Decisions","## Action Items","## Questions","## Keywords"];
    let labels=["## 会议摘要","## 决定","## 待办事项","## 待确认问题","## 关键词"];
    let mut indices=vec![start+7];
    for heading in headings.iter().skip(1) {
        let Some(offset)=lines[indices.last().unwrap()+1..].iter().position(|line|line==heading) else {
            return lines.into_iter().map(str::to_owned).collect();
        };
        indices.push(indices.last().unwrap()+1+offset);
    }
    let generated=lines[start+2].trim_start_matches("Generated: ");
    let generated=chrono::DateTime::parse_from_rfc3339(generated)
        .map(|date|date.with_timezone(&chrono::Local).format("%Y-%m-%d %H:%M").to_string())
        .unwrap_or_else(|_|generated.to_owned());
    let duration=lines[start+3].trim_start_matches("Duration: ");
    let duration=duration.strip_suffix(" ms").and_then(|v|v.parse::<u64>().ok()).map(|ms|{
        let seconds=ms/1000;format!("{:02}:{:02}:{:02}",seconds/3600,(seconds/60)%60,seconds%60)
    }).unwrap_or_else(||duration.to_owned());
    let source=lines[start+4].trim_start_matches("Source: ");
    let source=match source {"derivedAudio"=>"编辑另存的录音","importedAudio"=>"导入的音频","boardDevice"=>"录音卡", "hostMicrophone"=>"电脑麦克风", "hostMeeting"=>"电脑会议", "importedTranscript"=>"导入的文字", _=>source};
    let engine=lines[start+5].trim_start_matches("Minutes engine: ");
    let engine=if engine.starts_with("llm_") {"AI 整理"} else if engine.starts_with("rules_") {"本地整理"} else {engine};
    let mut out=Vec::new();let mut i=0;
    while i<lines.len() {
        if i==start {
            out.extend([format!("生成时间：{generated}"),format!("时长：{duration}"),format!("来源：{source}"),format!("整理方式：{engine}"),String::new()]);
            i+=7;continue;
        }
        if let Some(pos)=indices.iter().position(|index|*index==i) {out.push(labels[pos].into());}
        else if indices.iter().any(|index|*index+1==i) && matches!(lines[i],"- None captured"|"None captured") {
            out.push(if lines[i].starts_with('-') {"- 暂无"} else {"暂无"}.into());
        } else {out.push(lines[i].to_owned());}
        i+=1;
    }
    out
}

