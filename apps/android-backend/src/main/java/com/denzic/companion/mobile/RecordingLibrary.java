package com.denzic.companion.mobile;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.zip.CRC32;

/** Local encoded segment inventory. Call on a worker thread. */
public final class RecordingLibrary {
    private RecordingLibrary() {}
    public enum State { VERIFIED, PARTIAL, DAMAGED }
    public static final class Entry {
        public final RecorderWire.Descriptor descriptor;
        public final State state;
        public final Path file;
        private Entry(RecorderWire.Descriptor descriptor, State state, Path file) {
            this.descriptor=descriptor; this.state=state; this.file=file;
        }
    }
    public enum SessionState { COMPLETE, INCOMPLETE, DAMAGED }
    /** Segments are grouped by device identity, format epoch and session ID. */
    public static final class Session {
        public final SessionState state;
        public final List<Entry> segments;
        public final long startedUnixSeconds;
        public final ImportedAudio imported;
        public String key(){return imported!=null?imported.key:MeetingStore.sessionKey(segments.get(0).descriptor);}
        private Session(ImportedAudio value){state=SessionState.COMPLETE;segments=Collections.emptyList();startedUnixSeconds=0;imported=value;}
        private Session(SessionState state,List<Entry> entries) {
            this.imported=null;this.state=state;this.segments=Collections.unmodifiableList(new ArrayList<>(entries));
            long date=0;for(Entry e:entries)if(e.descriptor.startedUnixSeconds!=0){date=e.descriptor.startedUnixSeconds;break;}
            this.startedUnixSeconds=date;
        }
    }
    /** A metadata file that could not be read; neither it nor its audio is modified. */
    public static final class MetadataProblem {
        public final Path file;
        public final String detail;
        private MetadataProblem(Path file,String detail){this.file=file;this.detail=detail;}
    }
    /** Usable sessions and individual metadata errors for display by the host app. */
    public static final class Inventory {
        public final List<Session> sessions;
        public final List<MetadataProblem> problems;
        private Inventory(List<Session> sessions,List<MetadataProblem> problems){
            this.sessions=sessions;this.problems=Collections.unmodifiableList(new ArrayList<>(problems));
        }
    }

    /** Group verified and partial local copies into recordings without connecting to the device. */
    public static List<Session> sessions(Path directory) throws IOException {
        return sessions(directory,null);
    }
    /** Restrict a transfer to the selected session, leaving other recordings untouched. */
    static List<Session> sessions(Path directory,RecorderWire.Descriptor selected) throws IOException {
        return groupSessions(list(directory,selected));
    }
    /** Inspect other recordings even when an individual metadata file is damaged. */
    public static Inventory inspect(Path directory) throws IOException {
        return inspectMatching(directory,null);
    }
    /** Verify one selected session without reading any other recording's audio. */
    public static Inventory inspectSession(Path directory,String key)throws IOException {
        if(ImportedAudio.validKey(key)){List<Session> found=new ArrayList<>();List<MetadataProblem> issues=new ArrayList<>();Path p=directory.resolve(ImportedAudio.folder(key));if(Files.exists(p,LinkOption.NOFOLLOW_LINKS))try{found.add(new Session(ImportedAudio.read(p)));}catch(IOException e){issues.add(new MetadataProblem(p,e.getMessage()));}return new Inventory(Collections.unmodifiableList(found),issues);}
        if(key==null||!key.matches("[0-9a-f]{24}:(0|[1-9a-f][0-9a-f]{0,15}):(0|[1-9a-f][0-9a-f]{0,15})"))
            throw new IllegalArgumentException("canonical recording key required");
        return inspectMatching(directory,key.replace(':','-')+"-");
    }
    private static Inventory inspectMatching(Path directory,String selectedPrefix)throws IOException {
        if(directory==null)throw new IllegalArgumentException("directory required");
        List<Entry> entries=new ArrayList<>();List<MetadataProblem> problems=new ArrayList<>();
        if(Files.exists(directory))try(DirectoryStream<Path> files=Files.newDirectoryStream(directory,"*.meta")) {
            for(Path metadata:files) {
                if(selectedPrefix!=null&&!metadata.getFileName().toString().startsWith(selectedPrefix))continue;
                try {Entry entry=readEntry(directory,metadata);if(entry!=null)entries.add(entry);}
                catch(IOException error){problems.add(new MetadataProblem(metadata,error.getMessage()==null?"无法读取录音资料":error.getMessage()));}
            }
        }
        List<Session> sessions=new ArrayList<>();
        for(Session session:groupSessions(entries)) {
            String prefix=SegmentReceiver.sessionPrefix(session.segments.get(0).descriptor);boolean damaged=false;
            for(MetadataProblem problem:problems)if(problem.file.getFileName().toString().startsWith(prefix)){damaged=true;break;}
            sessions.add(damaged?new Session(SessionState.DAMAGED,session.segments):session);
        }
        if(selectedPrefix==null&&Files.exists(directory))try(DirectoryStream<Path> imports=Files.newDirectoryStream(directory,"import-*")){for(Path folder:imports){if(!folder.getFileName().toString().matches("import-[0-9a-f]{64}"))continue;try{sessions.add(new Session(ImportedAudio.read(folder)));}catch(IOException error){problems.add(new MetadataProblem(folder,error.getMessage()));}}}
        return new Inventory(Collections.unmodifiableList(sessions),problems);
    }
    /** The exact previously selected segment whose device confirmation is unresolved, or null. */
    public static RecorderWire.Descriptor pendingConfirmation(Path directory) throws IOException {
        if(directory==null)throw new IllegalArgumentException("directory required");
        Path pending=directory.resolve(".consume-pending");
        if(!Files.exists(pending,LinkOption.NOFOLLOW_LINKS))return null;
        if(!Files.isRegularFile(pending,LinkOption.NOFOLLOW_LINKS)||Files.size(pending)!=112)
            throw new IOException("pending recording confirmation is invalid; originals retained");
        return RecorderWire.Descriptor.decode(Files.readAllBytes(pending));
    }
    /** A receipt intentionally postponed by the user; this says nothing about the device copy. */
    public static final class DeferredConfirmation {
        public final String token;
        public final RecorderWire.Descriptor descriptor;
        private DeferredConfirmation(String token,RecorderWire.Descriptor descriptor){this.token=token;this.descriptor=descriptor;}
    }
    /** List postponed receipts so a host can offer a later retry. */
    public static List<DeferredConfirmation> deferredConfirmations(Path directory) throws IOException {
        if(directory==null)throw new IllegalArgumentException("directory required");
        List<DeferredConfirmation> result=new ArrayList<>();
        if(!Files.exists(directory))return Collections.emptyList();
        try(DirectoryStream<Path> files=Files.newDirectoryStream(directory,".consume-deferred-*.pending")) {
            for(Path file:files) {
                String token=file.getFileName().toString();
                if(!token.matches("\\.consume-deferred-[0-9a-f-]{36}\\.pending")||!Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS)||Files.size(file)!=112)
                    throw new IOException("暂缓的录音确认资料无法读取，已保存的录音保留");
                result.add(new DeferredConfirmation(token,RecorderWire.Descriptor.decode(Files.readAllBytes(file))));
            }
        }
        return Collections.unmodifiableList(result);
    }
    /** Move an unresolved receipt aside without changing local audio or the device. */
    public static String deferPendingConfirmation(Path directory,RecorderWire.Descriptor expected) throws IOException {
        return DurableConsume.defer(directory,expected,AndroidDirectorySync::sync);
    }
    /** Explicitly set an unreadable pending record aside; its bytes and unknown identity remain local. */
    public static String deferUnreadablePendingConfirmation(Path directory) throws IOException {
        return DurableConsume.deferUnreadable(directory,AndroidDirectorySync::sync);
    }
    /** List unreadable records preserved for support; they cannot authorize device consumption. */
    public static List<String> unreadableConfirmations(Path directory) throws IOException {
        if(directory==null)throw new IllegalArgumentException("directory required");
        if(!Files.exists(directory))return Collections.emptyList();
        List<String> result=new ArrayList<>();
        try(DirectoryStream<Path> files=Files.newDirectoryStream(directory,".consume-unreadable-*.pending")) {
            for(Path file:files) {
                String token=file.getFileName().toString();
                if(token.matches("\\.consume-unreadable-[0-9a-f-]{36}\\.pending")&&Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS))result.add(token);
            }
        }
        Collections.sort(result);
        return Collections.unmodifiableList(result);
    }
    /** Restore a previously deferred receipt so the host can retry with the original device. */
    public static void restoreDeferredConfirmation(Path directory,String token,RecorderWire.Descriptor expected) throws IOException {
        DurableConsume.restore(directory,token,expected,AndroidDirectorySync::sync);
    }
    static boolean sameSession(RecorderWire.Descriptor a,RecorderWire.Descriptor b) {
        return a!=null&&b!=null&&a.epoch==b.epoch&&a.sessionId==b.sessionId
            &&a.sourceMode==b.sourceMode&&Arrays.equals(a.uid(),b.uid());
    }
    private static List<Session> groupSessions(List<Entry> allEntries) {
        Map<String,List<Entry>> groups=new LinkedHashMap<>();
        for(Entry entry:allEntries) {
            RecorderWire.Descriptor d=entry.descriptor;
            String identity=identity(d);
            List<Entry> entries=groups.get(identity);
            if(entries==null){entries=new ArrayList<>();groups.put(identity,entries);}
            entries.add(entry);
        }
        List<Session> sessions=new ArrayList<>();
        for(List<Entry> entries:groups.values()) {
            entries.sort(Comparator.comparingLong(e->e.descriptor.segmentIndex));
            boolean missing=false, damaged=false, terminal=false;long expectedOffset=0,previousIndex=-1;
            int sourceMode=entries.get(0).descriptor.sourceMode;Set<Long> ids=new HashSet<>();long date=0;
            for(int i=0;i<entries.size();i++) {
                Entry e=entries.get(i);RecorderWire.Descriptor d=e.descriptor;
                if(d.startedUnixSeconds!=0){if(date!=0&&date!=d.startedUnixSeconds)damaged=true;date=d.startedUnixSeconds;}
                if(e.state==State.DAMAGED)damaged=true;
                if(e.state==State.PARTIAL)missing=true;
                if(d.segmentIndex==previousIndex || terminal || !ids.add(d.recordingId) || d.sourceMode!=sourceMode)damaged=true;
                if((d.segmentIndex==0&&d.sampleOffset!=0) || (previousIndex>=0 &&
                        (d.sampleOffset<expectedOffset || (d.segmentIndex==previousIndex+1&&d.sampleOffset!=expectedOffset))))damaged=true;
                if(d.segmentIndex!=i || d.sampleOffset!=expectedOffset)missing=true;
                if((d.flags&2)!=0)terminal=true;
                if((d.flags&4)!=0)missing=true;
                expectedOffset=d.sampleOffset+d.sampleCount;previousIndex=d.segmentIndex;
            }
            if(!terminal)missing=true;
            sessions.add(new Session(damaged?SessionState.DAMAGED:missing?SessionState.INCOMPLETE:SessionState.COMPLETE,entries));
        }
        return Collections.unmodifiableList(sessions);
    }
    private static String identity(RecorderWire.Descriptor d) {
        StringBuilder uid=new StringBuilder();for(byte b:d.uid())uid.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
        return uid+":"+Long.toUnsignedString(d.epoch)+":"+Long.toUnsignedString(d.sessionId);
    }

    /** The exact contiguous local prefix ending at a selected sealed segment. */
    static Session verifiedPrefix(Path directory,RecorderWire.Descriptor selected) throws IOException {
        for(Session session:sessions(directory,selected)) {
            if(session.segments.isEmpty()||!identity(session.segments.get(0).descriptor).equals(identity(selected)))continue;
            return verifiedPrefix(session,selected);
        }
        throw new IOException("selected recording is not saved on this phone; device copy retained");
    }
    /** Reuse this same freshly verified immutable inventory, without a
     * second directory walk and second hash of every original segment. */
    static Session verifiedPrefix(Session session,RecorderWire.Descriptor selected)throws IOException {
            if(session.segments.isEmpty()||!identity(session.segments.get(0).descriptor).equals(identity(selected)))
                throw new IOException("selected recording is not saved on this phone; device copy retained");
            List<Entry> prefix=new ArrayList<>();long offset=0;
            for(Entry entry:session.segments) {
                RecorderWire.Descriptor d=entry.descriptor;
                if(d.segmentIndex>selected.segmentIndex)break;
                if(entry.state!=State.VERIFIED||d.segmentIndex!=prefix.size()||d.sampleOffset!=offset||d.sourceMode!=selected.sourceMode)
                    throw new IOException("recording prefix is incomplete or damaged; device copy retained");
                prefix.add(entry);offset=d.sampleOffset+d.sampleCount;
            }
            if(prefix.size()!=selected.segmentIndex+1 || !prefix.get(prefix.size()-1).descriptor.sameContent(selected))
                throw new IOException("selected recording is not durably saved; device copy retained");
            return new Session((selected.flags&2)!=0&&(selected.flags&4)==0?SessionState.COMPLETE:SessionState.INCOMPLETE,prefix);
    }

    /** Checks every complete copy against its device descriptor; never modifies files. */
    public static List<Entry> list(Path directory) throws IOException {
        return list(directory,null);
    }
    private static List<Entry> list(Path directory,RecorderWire.Descriptor selected) throws IOException {
        if(directory==null)throw new IllegalArgumentException("directory required");
        if(!Files.exists(directory))return Collections.emptyList();
        List<Entry> result=new ArrayList<>();
        String selectedPrefix=selected==null?null:SegmentReceiver.sessionPrefix(selected);
        try(DirectoryStream<Path> files=Files.newDirectoryStream(directory,"*.meta")) {
            for(Path metadata:files) {
                if(selectedPrefix!=null&&!metadata.getFileName().toString().startsWith(selectedPrefix))continue;
                Entry entry=readEntry(directory,metadata);if(entry!=null)result.add(entry);
            }
        }
        return Collections.unmodifiableList(result);
    }
    private static Entry readEntry(Path directory,Path metadata) throws IOException {
        if(Files.size(metadata)!=112&&Files.size(metadata)!=120)throw new IOException("invalid local recording metadata: "+metadata.getFileName());
        RecorderWire.Descriptor d=RecorderWire.Descriptor.decode(Files.readAllBytes(metadata));
        String key=SegmentReceiver.key(d);
        if(!metadata.getFileName().toString().equals(key+".meta"))throw new IOException("recording metadata filename does not match its contents");
        Path complete=directory.resolve(key+".cop1"),partial=directory.resolve(key+".part");
        if(Files.exists(complete))return new Entry(d,verified(complete,d)?State.VERIFIED:State.DAMAGED,complete);
        if(Files.exists(partial))return new Entry(d,Files.size(partial)<=d.encodedLength?State.PARTIAL:State.DAMAGED,partial);
        return null;
    }
    static boolean verified(Path file,RecorderWire.Descriptor d) throws IOException {
        if(Files.size(file)!=d.encodedLength)return false;
        MessageDigest sha;try{sha=MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}
        CRC32 crc=new CRC32();byte[] buffer=new byte[32768];
        try(InputStream in=Files.newInputStream(file)){int n;while((n=in.read(buffer))!=-1){sha.update(buffer,0,n);crc.update(buffer,0,n);}}
        return crc.getValue()==d.contentCrc&&Arrays.equals(sha.digest(),d.sha256());
    }
}
