package com.denzic.companion.mobile;
import java.util.List;
public final class MeetingPdfContentTest {
 private static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
 public static void main(String[] args){
  String saved="> 人工修订：新增负责人和时间请按实际安排确认。\n\n# 原会议名\n\nGenerated: public-fixture\nDuration: 15000 ms\nSource: hostMicrophone\nMinutes engine: llm_deepseek (final)\n\n## Summary\n- 核对原话\n\n## Decisions\n- 待核对：保留条件\n\n## Action Items\n- [x] 手机负责人明天下午3点完成核对\n\n## Questions\n- 为什么？\n\n## Keywords\n- 会议\n";
  String display=MeetingPdfContent.readableMetadata(saved);check(!display.contains("Generated:")&&!display.contains("llm_deepseek")&&!display.contains("# 原会议名"),"machine metadata exposed after rename");
  for(String value:new String[]{"人工修订","手机负责人明天下午3点","待核对：保留条件","为什么？","会议摘要","讨论结论（需核对）"})check(display.contains(value),"lost saved meeting content: "+value);
  String incomplete=saved.replace("## Questions","## Open issues");check(MeetingPdfContent.readableMetadata(incomplete).equals(incomplete),"partial lookalike was rewritten");
  String fenced="```markdown\n"+saved+"\n```";check(MeetingPdfContent.readableMetadata(fenced).equals(fenced),"code example was rewritten");
  List<MeetingPdfContent.Block> blocks=MeetingPdfContent.markdown("> 整理来源已变化\n\n## C#\n- [x] 完成\n- [ ] 待办\n普通 **加粗**\n```\n## 保留#与**原文**\n```");
  check(blocks.size()==6,"unexpected source block loss");check(blocks.get(0).kind==MeetingPdfContent.QUOTE&&blocks.get(0).text.contains("来源已变化"),"source warning lost");
  check(blocks.get(1).text.equals("C#"),"literal trailing hash removed");check(blocks.get(2).text.equals("已完成 · 完成")&&blocks.get(3).text.equals("待办 · 待办"),"task status lost");
  check(blocks.get(5).kind==MeetingPdfContent.CODE&&blocks.get(5).text.equals("## 保留#与**原文**"),"code content changed");
  List<MeetingPdfContent.Block> fields=MeetingPdfContent.markdown("- [x] 跟进实际安排 (owner: 手机负责人, due: 下周五（需确认）)");
  check(fields.size()==3&&fields.get(0).text.equals("已完成 · 跟进实际安排")&&fields.get(1).kind==MeetingPdfContent.DETAIL&&fields.get(1).text.equals("负责人：手机负责人")&&fields.get(2).text.equals("时间：下周五（需确认）"),"task values/status lost during readable field presentation");
  List<MeetingPdfContent.Block> literal=MeetingPdfContent.markdown("- 讨论字符串 (owner: 原样保留, due: 说明)");check(literal.size()==1&&literal.get(0).text.contains("owner:"),"ordinary prose reinterpreted");
  List<MeetingPdfContent.Block> ambiguous=MeetingPdfContent.markdown("- [ ] 原文 (owner: A, due: 字段, due: 其它)");check(ambiguous.size()==1&&ambiguous.get(0).text.contains("owner:"),"ambiguous task fields guessed");
  System.out.println("PASS saved content, manual/source warnings, completed state, renamed metadata, incomplete/code negatives; no Android layout/model claim");
 }
}
