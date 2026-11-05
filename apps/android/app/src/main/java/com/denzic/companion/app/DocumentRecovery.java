package com.denzic.companion.app;

/** Decisions for an export whose system picker outlived its original WebView. */
final class DocumentRecovery {
    private DocumentRecovery() {}
    static boolean isPickerFormat(String format) {
        return "pdf".equals(format) || "word".equals(format) || "mindmap".equals(format)
            || "audio".equals(format) || "audioZip".equals(format) || "marks".equals(format);
    }
    static String notice(boolean saved,boolean complete,String error) {
        if(error!=null && !error.isEmpty())return error;
        if(!saved)return "已取消保存。";
        if(!complete)return "已保存当前可用的部分，原录音仍保留。";
        return "文件已保存。";
    }
}
