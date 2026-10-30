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
import java.util.List;
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
    private static boolean verified(Path file,RecorderWire.Descriptor d) throws IOException {
        if(Files.size(file)!=d.encodedLength)return false;
        MessageDigest sha;try{sha=MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}
        CRC32 crc=new CRC32();byte[] buffer=new byte[32768];
        try(InputStream in=Files.newInputStream(file)){int n;while((n=in.read(buffer))!=-1){sha.update(buffer,0,n);crc.update(buffer,0,n);}}
        return crc.getValue()==d.contentCrc&&Arrays.equals(sha.digest(),d.sha256());
    }
}
