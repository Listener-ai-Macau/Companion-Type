package com.denzic.companion.mobile;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.UUID;
public final class TransferPriorityScopeTest {
    static final class Link implements RecordingClient.Link {
        final ArrayList<Boolean> calls=new ArrayList<>();boolean rejected,gone,cleanupError;
        public int mtu(){return 512;}public byte[] read(UUID id){throw new AssertionError();}
        public void subscribe(UUID id){throw new AssertionError();}public void write(UUID id,byte[] b){throw new AssertionError();}
        public byte[] await(UUID id,long ms){throw new AssertionError();}public void close(){}
        public boolean disconnected(){return gone;}
        public boolean preferBulkTransfer(boolean active)throws IOException{calls.add(active);if(!active&&cleanupError)throw new IOException("cleanup");return !rejected;}
    }
    static void check(boolean b){if(!b)throw new AssertionError();}
    public static void main(String[] args)throws Exception {
        Link link=new Link();try(TransferPriorityScope p=TransferPriorityScope.open(link,true)){check(p.requested&&p.accepted);}
        check(link.calls.equals(Arrays.asList(true,false)));
        link=new Link();try(TransferPriorityScope p=TransferPriorityScope.open(link,false)){check(!p.requested&&!p.accepted);}check(link.calls.isEmpty());
        link=new Link();link.rejected=true;try(TransferPriorityScope p=TransferPriorityScope.open(link,true)){check(!p.accepted);}check(link.calls.equals(Arrays.asList(true,false)));
        link=new Link();link.gone=true;try(TransferPriorityScope p=TransferPriorityScope.open(link,true)){}check(link.calls.equals(Arrays.asList(true)));
        link=new Link();link.cleanupError=true;IOException primary=new IOException("original storage proof failed");
        try(TransferPriorityScope p=TransferPriorityScope.open(link,true)){throw primary;}catch(IOException e){check(e==primary&&e.getSuppressed().length==1);}
        link=new Link();TransferPriorityScope p=TransferPriorityScope.open(link,true);p.close();p.close();check(link.calls.equals(Arrays.asList(true,false)));
        System.out.println("PASS actual-transfer high/balanced lifecycle, no-data polling unchanged, optional refusal, disconnected cleanup, original error preserved, no replay");
    }
}
