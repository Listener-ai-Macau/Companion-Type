package com.denzic.companion.mobile;
import java.io.Closeable;
import java.io.IOException;

/** Central connection preference for one real transfer, not a timing claim.
 * No-data live-follow polls leave the connection balanced. */
final class TransferPriorityScope implements Closeable {
    final boolean requested,accepted;private final RecordingClient.Link link;private boolean closed;
    private TransferPriorityScope(RecordingClient.Link link,boolean active)throws IOException {
        this.link=link;requested=active;accepted=active&&link.preferBulkTransfer(true);
    }
    static TransferPriorityScope open(RecordingClient.Link link,boolean active)throws IOException {
        if(link==null)throw new IllegalArgumentException("link required");return new TransferPriorityScope(link,active);
    }
    @Override public void close()throws IOException {
        if(closed)return;closed=true;
        if(!requested||link.disconnected()||!link.isConnected())return;
        try{link.preferBulkTransfer(false);}
        catch(RecordingSyncRunner.LinkFailure gone){/* A disconnected owner cannot retain a connection priority. */}
    }
}
