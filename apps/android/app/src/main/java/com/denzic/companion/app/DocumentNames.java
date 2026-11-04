package com.denzic.companion.app;

/** Safe display names for user-selected audio exports. */
final class DocumentNames {
    private DocumentNames() {}
    static String audio(String title,boolean multiple) {
        String base=title==null?"":title.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]", " ").trim();
        base=base.replaceAll("[. ]+$", "").trim();
        if(base.isEmpty() || ".".equals(base) || "..".equals(base))base="Companion-录音";
        int count=base.codePointCount(0,base.length());
        if(count>80)base=base.substring(0,base.offsetByCodePoints(0,80)).trim();
        if(base.isEmpty())base="Companion-录音";
        if(base.matches("(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\\..*)?$"))base="录音-"+base;
        return base+(multiple?"-分段.zip":".wav");
    }
}
