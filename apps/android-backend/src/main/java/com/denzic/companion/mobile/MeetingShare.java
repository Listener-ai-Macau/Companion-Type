package com.denzic.companion.mobile;

import android.content.ClipData;
import android.content.Intent;
import android.net.Uri;

/** Builds a share intent; the host obtains a content URI and lets the user choose a recipient. */
public final class MeetingShare {
    private MeetingShare() {}
    public static Intent file(Uri contentUri,String mimeType) {
        if(contentUri==null||!"content".equalsIgnoreCase(contentUri.getScheme())||mimeType==null||mimeType.trim().isEmpty())
            throw new IllegalArgumentException("content URI and MIME type required");
        Intent intent=new Intent(Intent.ACTION_SEND);
        intent.setType(mimeType);intent.putExtra(Intent.EXTRA_STREAM,contentUri);
        intent.setClipData(ClipData.newRawUri("meeting",contentUri));
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        return intent;
    }
}
