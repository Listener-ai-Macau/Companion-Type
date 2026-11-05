package com.denzic.companion.mobile;

import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.pdf.PdfDocument;
import android.text.Layout;
import android.text.StaticLayout;
import android.text.TextPaint;
import java.io.IOException;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;

/** Local PDF output for saved meeting data. Call on a worker thread. */
public final class MeetingPdf {
    private static final int PAGE_WIDTH=595, PAGE_HEIGHT=842, MARGIN=48;
    private static final int INK=Color.rgb(29,38,52), MUTED=Color.rgb(95,108,127), RULE=Color.rgb(215,222,231);
    private static final float TOP=67, BOTTOM=790;
    private MeetingPdf() {}

    public static final class Sections {
        public final boolean minutes,transcript,notesAndTasks;
        public Sections(boolean minutes,boolean transcript,boolean notesAndTasks) {
            if(!minutes&&!transcript&&!notesAndTasks)throw new IllegalArgumentException("choose at least one section");
            this.minutes=minutes;this.transcript=transcript;this.notesAndTasks=notesAndTasks;
        }
    }

    /** Writes a PDF to the caller's stream without closing it or sending any content. */
    public static void write(String title,MeetingStore.Minutes minutes,MeetingStore.Snapshot meeting,
                             Sections sections,OutputStream output) throws IOException {
        write(title,minutes,meeting,sections,output,null);
    }

    /** The host supplies the bundled document font to preserve distinct Unicode
     * characters whose glyphs would otherwise alias in an OEM system font. */
    public static void write(String title,MeetingStore.Minutes minutes,MeetingStore.Snapshot meeting,
                             Sections sections,OutputStream output,Typeface documentTypeface) throws IOException {
        if(title==null||title.trim().isEmpty()||sections==null||output==null)
            throw new IllegalArgumentException("title, sections and output required");
        if(minutes!=null&&meeting!=null&&!minutes.sessionKey.equals(meeting.sessionKey))
            throw new IllegalArgumentException("meeting and minutes belong to different sessions");
        List<MeetingPdfContent.Block> blocks=new ArrayList<>();
        if(sections.minutes) {
            if(minutes==null)throw new IOException("没有已保存的会议纪要。");
            blocks.add(new MeetingPdfContent.Block(MeetingPdfContent.SECTION,"会议纪要"));
            blocks.addAll(MeetingPdfContent.markdown(NativeMeetingDocuments.savedText(minutes,meeting)));
        }
        if(sections.transcript) {
            if(meeting==null||meeting.transcript==null||meeting.transcript.trim().isEmpty())
                throw new IOException("没有已保存的会议转写。");
            blocks.add(new MeetingPdfContent.Block(MeetingPdfContent.SECTION,"会议转写"));
            // Transcripts are literal text, not Markdown. A spoken '# ' stays text.
            for(String line:meeting.transcript.split("\\r?\\n"))if(!line.trim().isEmpty())blocks.add(new MeetingPdfContent.Block(MeetingPdfContent.BODY,line));
        }
        if(sections.notesAndTasks) {
            if(meeting==null)throw new IOException("没有已保存的会议补充或任务。");
            boolean hasNotes=meeting.notes!=null&&!meeting.notes.trim().isEmpty();
            if(!hasNotes&&meeting.tasks.isEmpty())throw new IOException("没有已保存的会议补充或任务。");
            if(hasNotes){blocks.add(new MeetingPdfContent.Block(MeetingPdfContent.SECTION,"用户补充"));for(String line:meeting.notes.split("\\r?\\n"))if(!line.trim().isEmpty())blocks.add(new MeetingPdfContent.Block(MeetingPdfContent.BODY,line));}
            if(!meeting.tasks.isEmpty()) {
                blocks.add(new MeetingPdfContent.Block(MeetingPdfContent.SECTION,"当前任务"));
                for(MeetingStore.Task task:meeting.tasks) {
                    StringBuilder text=new StringBuilder();
                    text.append(task.completed?"[已完成] ":"[待办] ").append(task.text);
                    if(task.owner!=null&&!task.owner.trim().isEmpty())text.append(" 负责人：").append(task.owner);
                    if(task.due!=null&&!task.due.trim().isEmpty())text.append(" 时间：").append(task.due);
                    blocks.add(new MeetingPdfContent.Block(MeetingPdfContent.BULLET,text.toString()));
                }
            }
        }
        writeBlocks(title.trim(),blocks,output,documentTypeface);
    }

    private static TextPaint paint(float size,boolean bold,int color,Typeface documentTypeface){
        TextPaint result=new TextPaint(Paint.ANTI_ALIAS_FLAG);result.setColor(color);result.setTextSize(size);
        result.setTypeface(documentTypeface!=null?documentTypeface:Typeface.create("sans-serif",bold?Typeface.BOLD:Typeface.NORMAL));
        if(documentTypeface!=null){result.setFakeBoldText(bold);result.setFontFeatureSettings("'liga' 0, 'clig' 0, 'calt' 0, 'locl' 0");}
        return result;
    }
    public static void writeSelected(String title,List<MeetingDocumentSections.Section> sections,OutputStream output,Typeface font)throws IOException{
        if(title==null||title.trim().isEmpty()||sections==null||sections.isEmpty()||output==null)throw new IOException("请选择有效的导出内容。");
        List<MeetingPdfContent.Block> blocks=new ArrayList<>();List<List<MeetingPdfContent.Block>> groups=new ArrayList<>();
        for(MeetingDocumentSections.Section section:sections){
            List<MeetingPdfContent.Block> group=new ArrayList<>();group.add(new MeetingPdfContent.Block(MeetingPdfContent.SECTION,section.title));
            if(section.markdown)group.addAll(MeetingPdfContent.markdown(section.text));
            else for(String line:section.text.split("\\r?\\n",-1))group.add(new MeetingPdfContent.Block(MeetingPdfContent.BODY,line.isEmpty()?" ":line));
            blocks.addAll(group);groups.add(section.text.length()<=1500?group:null);
        }
        writeBlocks(title.trim(),blocks,output,font,groups);
    }
    private static StaticLayout layout(String text,TextPaint paint,int width){
        return StaticLayout.Builder.obtain(text,0,text.length(),paint,width).setAlignment(Layout.Alignment.ALIGN_NORMAL)
            .setIncludePad(false).setLineSpacing(2.5f,1.08f).setBreakStrategy(Layout.BREAK_STRATEGY_HIGH_QUALITY).build();
    }
    private static final class Fragment {
        final StaticLayout layout;final int first,end,kind;final float x,y,width;
        Fragment(StaticLayout l,int first,int end,int kind,float x,float y,float width){this.layout=l;this.first=first;this.end=end;this.kind=kind;this.x=x;this.y=y;this.width=width;}
        float height(){return layout.getLineBottom(end-1)-layout.getLineTop(first);}
    }
    private static final class Plan {
        final List<List<Fragment>> pages=new ArrayList<>();final Typeface documentTypeface;float y=TOP;
        Plan(Typeface documentTypeface){this.documentTypeface=documentTypeface;pages.add(new ArrayList<>());}
        void next(){pages.add(new ArrayList<>());y=TOP;}
        void add(MeetingPdfContent.Block block){
            int kind=block.kind;boolean heading=kind==MeetingPdfContent.HEADING||kind==MeetingPdfContent.SECTION;
            int indent=kind==MeetingPdfContent.BULLET||kind==MeetingPdfContent.DETAIL?14:kind==MeetingPdfContent.QUOTE?12:0;
            float before=heading?16:kind==MeetingPdfContent.DETAIL?0:3,after=heading?8:kind==MeetingPdfContent.QUOTE?10:kind==MeetingPdfContent.DETAIL?2:5;
            TextPaint p=paint(kind==MeetingPdfContent.SECTION?16:heading?13:kind==MeetingPdfContent.QUOTE||kind==MeetingPdfContent.DETAIL?10:11,heading,kind==MeetingPdfContent.QUOTE||kind==MeetingPdfContent.DETAIL?MUTED:INK,documentTypeface);
            if(kind==MeetingPdfContent.CODE&&documentTypeface==null)p.setTypeface(Typeface.MONOSPACE);
            StaticLayout text=layout(block.text,p,PAGE_WIDTH-2*MARGIN-indent-(kind==MeetingPdfContent.QUOTE?8:0));
            int first=0,count=text.getLineCount();
            // Keep a normal heading with at least two lines of following content.
            if(heading&&y+before+text.getHeight()+after+38>BOTTOM)next();
            y+=before;
            while(first<count){
                int end=first;
                while(end<count&&y+text.getLineBottom(end)-text.getLineTop(first)+(kind==MeetingPdfContent.QUOTE?6:0)<=BOTTOM)end++;
                if(end==first){next();continue;}
                Fragment fragment=new Fragment(text,first,end,kind,MARGIN+indent,y,PAGE_WIDTH-2*MARGIN-indent);
                pages.get(pages.size()-1).add(fragment);y+=fragment.height();first=end;
                if(first<count)next();
            }
            y+=after;
        }
    }
    private static void writeBlocks(String title,List<MeetingPdfContent.Block> blocks,OutputStream output,Typeface documentTypeface)throws IOException{
        writeBlocks(title,blocks,output,documentTypeface,null);
    }
    private static void writeBlocks(String title,List<MeetingPdfContent.Block> blocks,OutputStream output,Typeface documentTypeface,List<List<MeetingPdfContent.Block>> selectedGroups)throws IOException{
        Plan plan=new Plan(documentTypeface);
        StaticLayout titleLayout=layout(title,paint(23,true,INK,documentTypeface),PAGE_WIDTH-2*MARGIN);
        // The same line-aware pagination also handles unusually long user titles.
        int first=0;
        while(first<titleLayout.getLineCount()){
            int end=first;while(end<titleLayout.getLineCount()&&plan.y+titleLayout.getLineBottom(end)-titleLayout.getLineTop(first)<=BOTTOM-45)end++;
            if(end==first){plan.next();continue;}
            Fragment fragment=new Fragment(titleLayout,first,end,-1,MARGIN,plan.y,PAGE_WIDTH-2*MARGIN);plan.pages.get(plan.pages.size()-1).add(fragment);plan.y+=fragment.height()+12;first=end;
            if(first<titleLayout.getLineCount())plan.next();
        }
        int position=0;
        if(selectedGroups!=null){
            for(List<MeetingPdfContent.Block> group:selectedGroups){
                if(group==null){
                    // A long section is streamed through the existing paginator.
                    do{plan.add(blocks.get(position++));}while(position<blocks.size()&&blocks.get(position).kind!=MeetingPdfContent.SECTION);
                }else{
                    Plan measured=new Plan(documentTypeface);for(MeetingPdfContent.Block block:group)measured.add(block);
                    float height=measured.y-TOP;
                    // Keep a compact section, such as a task and its person/date,
                    // together. Long sections retain line-aware pagination.
                    if(measured.pages.size()==1&&height<=180&&plan.y+height>BOTTOM)plan.next();
                    for(MeetingPdfContent.Block block:group){plan.add(block);position++;}
                }
            }
        }else for(MeetingPdfContent.Block block:blocks)plan.add(block);
        PdfDocument document=new PdfDocument();
        try {
            for(int page=0;page<plan.pages.size();page++){
                PdfDocument.Page current=document.startPage(new PdfDocument.PageInfo.Builder(PAGE_WIDTH,PAGE_HEIGHT,page+1).create());Canvas canvas=current.getCanvas();
                canvas.drawText("COMPANION  /  MEETING NOTES",MARGIN,32,paint(8,true,MUTED,documentTypeface));
                Paint rule=new Paint();rule.setColor(RULE);rule.setStrokeWidth(.6f);canvas.drawLine(MARGIN,43,PAGE_WIDTH-MARGIN,43,rule);
                for(Fragment fragment:plan.pages.get(page)){
                    float height=fragment.height();
                    if(fragment.kind==MeetingPdfContent.QUOTE){Paint background=new Paint();background.setColor(Color.rgb(244,246,249));canvas.drawRect(MARGIN,fragment.y-3,PAGE_WIDTH-MARGIN,fragment.y+height+3,background);background.setColor(RULE);canvas.drawRect(MARGIN,fragment.y-3,MARGIN+2,fragment.y+height+3,background);}
                    if(fragment.kind==MeetingPdfContent.BULLET&&fragment.first==0){Paint bullet=new Paint(Paint.ANTI_ALIAS_FLAG);bullet.setColor(MUTED);canvas.drawCircle(MARGIN+3,fragment.y+fragment.layout.getLineBaseline(0)-4,1.8f,bullet);}
                    canvas.save();canvas.clipRect(fragment.x,fragment.y,fragment.x+fragment.width,fragment.y+height);
                    canvas.translate(fragment.x,fragment.y-fragment.layout.getLineTop(fragment.first));fragment.layout.draw(canvas);canvas.restore();
                }
                canvas.drawLine(MARGIN,804,PAGE_WIDTH-MARGIN,804,rule);canvas.drawText("会议资料 · 请结合原文核对",MARGIN,820,paint(8,false,MUTED,documentTypeface));
                TextPaint pagePaint=paint(8,false,MUTED,documentTypeface);String number=(page+1)+" / "+plan.pages.size();canvas.drawText(number,PAGE_WIDTH-MARGIN-pagePaint.measureText(number),820,pagePaint);
                document.finishPage(current);
            }
            document.writeTo(output);
        } finally {document.close();}
    }
}
