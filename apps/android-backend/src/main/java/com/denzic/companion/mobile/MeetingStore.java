package com.denzic.companion.mobile;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.DirectoryStream;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/** App-private text, notes and tasks for a recording session. Use from a worker thread. */
public final class MeetingStore {
    private static final int MAX_BYTES=16*1024*1024,MAX_TASKS=10_000;
    private final Path directory;
    public MeetingStore(Path appPrivateDirectory) {if(appPrivateDirectory==null)throw new IllegalArgumentException("private directory required");directory=appPrivateDirectory;}

    public static final class Task {
        public final String id,text,owner,due;
        public final boolean completed;
        public Task(String id,String text,String owner,String due,boolean completed) {
            if(id==null||id.isEmpty()||text==null||text.trim().isEmpty())throw new IllegalArgumentException("task id and text required");
            this.id=id;this.text=text;this.owner=owner;this.due=due;this.completed=completed;
        }
    }
    public static final class Snapshot {
        public final String sessionKey,transcript,notes;
        public final long revision;
        public final List<Task> tasks;
        /** True means the main file was missing/damaged and the previous version was recovered. */
        public final boolean recoveredFromBackup;
        private Snapshot(String key,long revision,String transcript,String notes,List<Task> tasks,boolean recovered) {
            this.sessionKey=key;this.revision=revision;this.transcript=transcript;this.notes=notes;
            this.tasks=Collections.unmodifiableList(new ArrayList<>(tasks));this.recoveredFromBackup=recovered;
        }
    }
    public static final class Inventory {
        public final List<Snapshot> meetings;
        /** Number of unreadable files or temporarily unavailable meetings; others remain available. */
        public final int unreadableFiles;
        private Inventory(List<Snapshot> meetings,int unreadableFiles) {
            this.meetings=Collections.unmodifiableList(new ArrayList<>(meetings));this.unreadableFiles=unreadableFiles;
        }
    }
    /** Stable across all sealed segments of one device session. */
    public static String sessionKey(RecorderWire.Descriptor descriptor) {
        if(descriptor==null)throw new IllegalArgumentException("descriptor required");
        return hex(descriptor.uid())+":"+Long.toUnsignedString(descriptor.epoch,16)+":"+Long.toUnsignedString(descriptor.sessionId,16);
    }
    private static MessageDigest digest(){try{return MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}}
    private static String hex(byte[] bytes){StringBuilder s=new StringBuilder(bytes.length*2);for(byte b:bytes)s.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return s.toString();}
    private Path path(String key,String extension) {
        if(key==null||key.isEmpty())throw new IllegalArgumentException("session key required");
        return directory.resolve(hex(digest().digest(key.getBytes(StandardCharsets.UTF_8)))+extension);
    }
    private interface Operation<T>{T run() throws IOException;}
    private <T> T locked(String key,Operation<T> action) throws IOException {
        Files.createDirectories(directory);
        try(RandomAccessFile lockFile=new RandomAccessFile(path(key,".lock").toFile(),"rw");FileChannel channel=lockFile.getChannel()) {
            FileLock lock;
            try{lock=channel.tryLock();}catch(OverlappingFileLockException e){throw new IOException("meeting is being saved; try again",e);}
            if(lock==null)throw new IOException("meeting is being saved; try again");
            try{return action.run();}finally{lock.release();}
        }
    }
    /** Returns null for a session with no saved text or tasks. */
    public Snapshot load(String key) throws IOException {return locked(key,()->loadLocked(key));}
    /** List saved meetings even when their recording device is disconnected. */
    public Inventory list() throws IOException {
        if(!Files.exists(directory))return new Inventory(Collections.emptyList(),0);
        Set<String> keys=new LinkedHashSet<>();int unreadable=0;
        for(String extension:new String[]{".meeting",".backup"}) {
            try(DirectoryStream<Path> files=Files.newDirectoryStream(directory,"*"+extension)) {
                for(Path file:files) {
                    try {
                        Snapshot value=read(file,null,false);
                        if(!file.getFileName().equals(path(value.sessionKey,extension).getFileName()))throw new IOException("saved meeting identity mismatch");
                        keys.add(value.sessionKey);
                    } catch(IOException error){unreadable++;}
                }
            }
        }
        List<Snapshot> values=new ArrayList<>();
        for(String key:keys){try{Snapshot value=load(key);if(value!=null)values.add(value);}catch(IOException error){unreadable++;}}
        values.sort((a,b)->a.sessionKey.compareTo(b.sessionKey));
        return new Inventory(values,unreadable);
    }
    private Snapshot loadLocked(String key) throws IOException {
        Path current=path(key,".meeting"),backup=path(key,".backup");
        IOException mainError=null;
        if(Files.exists(current)) {
            try{return read(current,key,false);}catch(IOException e){mainError=e;}
        }
        if(Files.exists(backup)) {
            try{return read(backup,key,true);}catch(IOException e){if(mainError!=null)e.addSuppressed(mainError);throw e;}
        }
        if(mainError!=null)throw mainError;
        return null;
    }
    /** Revision 0 creates a new meeting. A stale revision leaves the saved content untouched. */
    public Snapshot save(String key,long expectedRevision,String transcript,String notes,List<Task> tasks) throws IOException {
        if(transcript==null||notes==null||tasks==null||expectedRevision<0)throw new IllegalArgumentException("content and revision required");
        List<Task> copy=new ArrayList<>(tasks);
        if(copy.size()>MAX_TASKS)throw new IOException("too many tasks");
        Set<String> ids=new HashSet<>();for(Task task:copy)if(task==null||!ids.add(task.id))throw new IOException("task identifiers must be unique");
        return locked(key,()->{
            Snapshot previous=loadLocked(key);long revision=previous==null?0:previous.revision;
            if(revision!=expectedRevision)throw new IOException("meeting changed; reload before saving");
            if(revision==Long.MAX_VALUE)throw new IOException("meeting revision limit reached");
            Snapshot next=new Snapshot(key,revision+1,transcript,notes,copy,false);byte[] bytes=encode(next);
            Path current=path(key,".meeting"),backup=path(key,".backup");
            Path temp=Files.createTempFile(directory,".meeting-",".tmp");
            try {
                writeDurable(temp,bytes);
                if(previous!=null&&!previous.recoveredFromBackup) {
                    Path backupTemp=Files.createTempFile(directory,".meeting-backup-",".tmp");
                    try{writeDurable(backupTemp,Files.readAllBytes(current));Files.move(backupTemp,backup,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
                    finally{Files.deleteIfExists(backupTemp);}
                } else if(previous!=null&&Files.exists(current)) {
                    Path damaged=directory.resolve("damaged-meeting-"+UUID.randomUUID()+".bin");
                    Files.move(current,damaged,StandardCopyOption.ATOMIC_MOVE);
                }
                Files.move(temp,current,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
                return next;
            } finally {Files.deleteIfExists(temp);}
        });
    }
    private static void writeDurable(Path path,byte[] bytes)throws IOException {
        try(RandomAccessFile f=new RandomAccessFile(path.toFile(),"rw")){f.write(bytes);f.getFD().sync();}
    }
    private static void string(DataOutputStream out,String text)throws IOException {
        if(text==null){out.writeInt(-1);return;}byte[] bytes=text.getBytes(StandardCharsets.UTF_8);if(bytes.length>MAX_BYTES)throw new IOException("text is too large");out.writeInt(bytes.length);out.write(bytes);
    }
    private static final class LimitedOutput extends OutputStream {
        final ByteArrayOutputStream buffer=new ByteArrayOutputStream();
        @Override public void write(int value)throws IOException {if(buffer.size()>=MAX_BYTES-32)throw new IOException("meeting content is too large");buffer.write(value);}
        @Override public void write(byte[] bytes,int offset,int length)throws IOException {if(length>MAX_BYTES-32-buffer.size())throw new IOException("meeting content is too large");buffer.write(bytes,offset,length);}
    }
    private static String string(DataInputStream in)throws IOException {
        int size=in.readInt();if(size==-1)return null;if(size<0||size>MAX_BYTES||size>in.available())throw new IOException("invalid saved text");byte[] bytes=new byte[size];in.readFully(bytes);
        try{return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();}
        catch(CharacterCodingException e){throw new IOException("invalid saved text encoding",e);}
    }
    private static byte[] encode(Snapshot value)throws IOException {
        LimitedOutput limited=new LimitedOutput();ByteArrayOutputStream buffer=limited.buffer;DataOutputStream out=new DataOutputStream(limited);
        out.writeInt(0x434d5731);string(out,value.sessionKey);out.writeLong(value.revision);string(out,value.transcript);string(out,value.notes);out.writeInt(value.tasks.size());
        for(Task task:value.tasks){string(out,task.id);string(out,task.text);string(out,task.owner);string(out,task.due);out.writeBoolean(task.completed);}
        out.flush();byte[] body=buffer.toByteArray();if(body.length>MAX_BYTES-32)throw new IOException("meeting content is too large");buffer.write(digest().digest(body));return buffer.toByteArray();
    }
    private static Snapshot read(Path path,String key,boolean recovered)throws IOException {
        long size=Files.size(path);if(size<36||size>MAX_BYTES)throw new IOException("saved meeting is damaged");byte[] bytes=Files.readAllBytes(path);if(bytes.length!=size)throw new IOException("saved meeting changed while reading");
        int n=bytes.length-32;MessageDigest h=digest();h.update(bytes,0,n);if(!MessageDigest.isEqual(h.digest(),java.util.Arrays.copyOfRange(bytes,n,bytes.length)))throw new IOException("saved meeting is damaged");
        DataInputStream in=new DataInputStream(new ByteArrayInputStream(bytes,0,n));if(in.readInt()!=0x434d5731)throw new IOException("unsupported meeting format");
        String savedKey=string(in);long revision=in.readLong();String transcript=string(in),notes=string(in);int count=in.readInt();
        if(savedKey==null||savedKey.isEmpty()||(key!=null&&!key.equals(savedKey))||revision<=0||transcript==null||notes==null||count<0||count>MAX_TASKS)throw new IOException("invalid saved meeting");
        List<Task> tasks=new ArrayList<>();Set<String> ids=new HashSet<>();
        try{for(int i=0;i<count;i++){Task task=new Task(string(in),string(in),string(in),string(in),in.readBoolean());if(!ids.add(task.id))throw new IOException("duplicate saved task");tasks.add(task);}}
        catch(IllegalArgumentException e){throw new IOException("invalid saved task",e);}
        if(in.available()!=0)throw new IOException("unexpected saved meeting data");return new Snapshot(savedKey,revision,transcript,notes,tasks,recovered);
    }
}
