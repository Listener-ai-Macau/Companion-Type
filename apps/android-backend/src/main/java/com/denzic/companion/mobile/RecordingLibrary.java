package com.denzic.companion.mobile;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
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
        private Session(SessionState state,List<Entry> entries) {
            this.state=state;this.segments=Collections.unmodifiableList(new ArrayList<>(entries));
        }
    }

    /** Group verified and partial local copies into recordings without connecting to the device. */
    public static List<Session> sessions(Path directory) throws IOException {
        Map<String,List<Entry>> groups=new LinkedHashMap<>();
        for(Entry entry:list(directory)) {
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
            int sourceMode=entries.get(0).descriptor.sourceMode;Set<Long> ids=new HashSet<>();
            for(int i=0;i<entries.size();i++) {
                Entry e=entries.get(i);RecorderWire.Descriptor d=e.descriptor;
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
        for(Session session:sessions(directory)) {
            if(session.segments.isEmpty()||!identity(session.segments.get(0).descriptor).equals(identity(selected)))continue;
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
        throw new IOException("selected recording is not saved on this phone; device copy retained");
    }

    /** Checks every complete copy against its device descriptor; never modifies files. */
    public static List<Entry> list(Path directory) throws IOException {
        if(directory==null)throw new IllegalArgumentException("directory required");
        if(!Files.exists(directory))return Collections.emptyList();
        List<Entry> result=new ArrayList<>();
        try(DirectoryStream<Path> files=Files.newDirectoryStream(directory,"*.meta")) {
            for(Path metadata:files) {
                if(Files.size(metadata)!=112)throw new IOException("invalid local recording metadata: "+metadata.getFileName());
                RecorderWire.Descriptor d=RecorderWire.Descriptor.decode(Files.readAllBytes(metadata));
                String key=SegmentReceiver.key(d);
                if(!metadata.getFileName().toString().equals(key+".meta"))throw new IOException("recording metadata filename does not match its contents");
                Path complete=directory.resolve(key+".cop1"),partial=directory.resolve(key+".part");
                if(Files.exists(complete))result.add(new Entry(d,verified(complete,d)?State.VERIFIED:State.DAMAGED,complete));
                else if(Files.exists(partial))result.add(new Entry(d,Files.size(partial)<=d.encodedLength?State.PARTIAL:State.DAMAGED,partial));
            }
        }
        return Collections.unmodifiableList(result);
    }
    static boolean verified(Path file,RecorderWire.Descriptor d) throws IOException {
        if(Files.size(file)!=d.encodedLength)return false;
        MessageDigest sha;try{sha=MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}
        CRC32 crc=new CRC32();byte[] buffer=new byte[32768];
        try(InputStream in=Files.newInputStream(file)){int n;while((n=in.read(buffer))!=-1){sha.update(buffer,0,n);crc.update(buffer,0,n);}}
        return crc.getValue()==d.contentCrc&&Arrays.equals(sha.digest(),d.sha256());
    }
}
