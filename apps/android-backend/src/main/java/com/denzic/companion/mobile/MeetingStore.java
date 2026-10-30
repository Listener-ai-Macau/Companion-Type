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

    /** Explicit calendar choices, retained with the task until the user changes them. */
    public static final class CalendarSettings {
        public final Integer reminderMinutes;public final String reminderAt,slotStart,slotEnd,selectedForDue;
        private final boolean recoveredForReview;
        public CalendarSettings(Integer minutes,String at,String start,String end){this(minutes,at,start,end,null);}
        private CalendarSettings(Integer minutes,String at,String start,String end,String due){this(minutes,at,start,end,due,false);}
        private CalendarSettings(Integer minutes,String at,String start,String end,String due,boolean recovered){
            if(minutes!=null&&(minutes!=0&&minutes!=30&&minutes!=60&&minutes!=1440))throw new IllegalArgumentException("unsupported reminder");
            if(minutes!=null&&at!=null)throw new IllegalArgumentException("choose one reminder");
            if((start==null)!=(end==null))throw new IllegalArgumentException("execution time needs a start and end");
            try {
                if(at!=null)java.time.OffsetDateTime.parse(at);
                if(start!=null&&!java.time.OffsetDateTime.parse(end).toInstant().isAfter(java.time.OffsetDateTime.parse(start).toInstant()))throw new IllegalArgumentException("invalid execution time");
            }catch(java.time.DateTimeException e){throw new IllegalArgumentException("calendar time needs a date and offset",e);}
            reminderMinutes=minutes;reminderAt=at;slotStart=start;slotEnd=end;selectedForDue=due;recoveredForReview=recovered;
        }
        private CalendarSettings selectedFor(String due){return new CalendarSettings(reminderMinutes,reminderAt,slotStart,slotEnd,due);}
        private CalendarSettings forReview(){return new CalendarSettings(reminderMinutes,reminderAt,slotStart,slotEnd,selectedForDue,true);}
    }
    public static final class Task {
        public final String id,text,owner,due;
        public final boolean completed;
        public final CalendarSettings calendar;
        private final boolean calendarSpecified;
        public Task(String id,String text,String owner,String due,boolean completed) {
            this(id,text,owner,due,completed,null,false);
        }
        /** Pass null to explicitly clear previously saved calendar choices. */
        public Task(String id,String text,String owner,String due,boolean completed,CalendarSettings calendar) {
            this(id,text,owner,due,completed,calendar==null?null:calendar.selectedFor(due),true);
        }
        private Task(String id,String text,String owner,String due,boolean completed,CalendarSettings calendar,boolean specified) {
            if(id==null||id.isEmpty()||text==null||text.trim().isEmpty())throw new IllegalArgumentException("task id and text required");
            this.id=id;this.text=text;this.owner=owner;this.due=due;this.completed=completed;this.calendar=calendar;this.calendarSpecified=specified;
        }
        /** A changed due date may require reviewing an existing reminder or execution slot. */
        public boolean calendarNeedsReview(){return calendar!=null&&(calendar.reminderMinutes!=null||calendar.reminderAt!=null||calendar.slotStart!=null)&&(calendar.recoveredForReview||!java.util.Objects.equals(due,calendar.selectedForDue));}
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
            try{return withCalendar(read(current,key,false),current);}catch(IOException e){mainError=e;}
        }
        if(Files.exists(backup)) {
            try{return withCalendar(read(backup,key,true),backup);}catch(IOException e){if(mainError!=null)e.addSuppressed(mainError);throw e;}
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
            java.util.Map<String,Task> old=new java.util.HashMap<>();if(previous!=null)for(Task task:previous.tasks)old.put(task.id,task);
            List<Task> merged=new ArrayList<>();for(Task task:copy){
                Task prior=old.get(task.id);CalendarSettings settings=task.calendarSpecified?task.calendar:prior==null?null:prior.calendar;
                merged.add(new Task(task.id,task.text,task.owner,task.due,task.completed,settings,true));
            }
            Snapshot next=new Snapshot(key,revision+1,transcript,notes,merged,false);byte[] bytes=encode(next);
            Path current=path(key,".meeting"),backup=path(key,".backup");
            Path temp=Files.createTempFile(directory,".meeting-",".tmp");
            try {
                writeDurable(temp,bytes);
                // Publish calendar choices first, retaining the preceding records.
                // A crash before the meeting move therefore leaves the old
                // meeting able to find its own choices by content hash.
                writeCalendar(key,next,bytes);
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
        DataInputStream in=new DataInputStream(new ByteArrayInputStream(bytes,0,n));int version=in.readInt();if(version!=0x434d5731&&version!=0x434d5732)throw new IOException("unsupported meeting format");
        String savedKey=string(in);long revision=in.readLong();String transcript=string(in),notes=string(in);int count=in.readInt();
        if(savedKey==null||savedKey.isEmpty()||(key!=null&&!key.equals(savedKey))||revision<=0||transcript==null||notes==null||count<0||count>MAX_TASKS)throw new IOException("invalid saved meeting");
        List<Task> tasks=new ArrayList<>();Set<String> ids=new HashSet<>();
        try{for(int i=0;i<count;i++){
            String id=string(in),text=string(in),owner=string(in),due=string(in);boolean completed=in.readBoolean();CalendarSettings calendar=null;
            if(version==0x434d5732&&in.readBoolean()){int minutes=in.readInt();if(minutes < -1)throw new IOException("invalid saved reminder");
                calendar=new CalendarSettings(minutes==-1?null:minutes,string(in),string(in),string(in),string(in));}
            Task task=new Task(id,text,owner,due,completed,calendar,true);if(!ids.add(task.id))throw new IOException("duplicate saved task");tasks.add(task);}}
        catch(IllegalArgumentException e){throw new IOException("invalid saved task",e);}
        if(in.available()!=0)throw new IOException("unexpected saved meeting data");return new Snapshot(savedKey,revision,transcript,notes,tasks,recovered);
    }

    // CMW1 remains readable by older backends. Calendar-only metadata is bound
    // to the exact meeting bytes, rather than just a revision number: an old
    // client may restore a backup and reuse a revision for different content.
    private static final class CalendarRecord {
        final byte[] meetingHash;final java.util.Map<String,CalendarSettings> values;
        CalendarRecord(byte[] hash,java.util.Map<String,CalendarSettings> settings){meetingHash=hash;values=settings;}
    }
    private List<CalendarRecord> readCalendar(String key)throws IOException {
        Path file=path(key,".calendar");if(!Files.exists(file))return new ArrayList<>();
        long size=Files.size(file);if(size<40||size>MAX_BYTES)throw new IOException("saved calendar choices are damaged; meeting remains unchanged");
        byte[] bytes=Files.readAllBytes(file);if(bytes.length!=size)throw new IOException("saved calendar choices changed while reading");
        int n=bytes.length-32;MessageDigest hash=digest();hash.update(bytes,0,n);
        if(!MessageDigest.isEqual(hash.digest(),java.util.Arrays.copyOfRange(bytes,n,bytes.length)))throw new IOException("saved calendar choices are damaged; meeting remains unchanged");
        DataInputStream in=new DataInputStream(new ByteArrayInputStream(bytes,0,n));
        int version=in.readInt();if(version!=0x43435331&&version!=0x43435332)throw new IOException("unsupported calendar choices format");
        String savedKey=string(in);int count=in.readInt();
        if(!key.equals(savedKey)||count<0||count>3)throw new IOException("invalid calendar choices identity");
        List<CalendarRecord> result=new ArrayList<>();Set<String> hashes=new HashSet<>();
        try {
            for(int i=0;i<count;i++){
                byte[] fingerprint=new byte[32];in.readFully(fingerprint);if(!hashes.add(hex(fingerprint)))throw new IOException("duplicate calendar choices version");
                int taskCount=in.readInt();if(taskCount<0||taskCount>MAX_TASKS)throw new IOException("invalid calendar choices count");
                java.util.Map<String,CalendarSettings> values=new java.util.HashMap<>();
                for(int j=0;j<taskCount;j++){
                    String id=string(in);int minutes=in.readInt();if(id==null||id.isEmpty()||minutes < -1)throw new IOException("invalid calendar choices");
                    String at=string(in),start=string(in),end=string(in),due=string(in);boolean review=version==0x43435332&&in.readBoolean();
                    CalendarSettings settings=new CalendarSettings(minutes==-1?null:minutes,at,start,end,due,review);
                    if(values.put(id,settings)!=null)throw new IOException("duplicate calendar task");
                }
                result.add(new CalendarRecord(fingerprint,values));
            }
        }catch(IllegalArgumentException e){throw new IOException("invalid calendar choices",e);}
        if(in.available()!=0)throw new IOException("unexpected calendar choices data");return result;
    }
    private Snapshot withCalendar(Snapshot snapshot,Path meeting)throws IOException {
        byte[] bytes=Files.readAllBytes(meeting);
        if(bytes.length<4||ByteBuffer.wrap(bytes,0,4).getInt()!=0x434d5731)return snapshot;
        byte[] fingerprint=digest().digest(bytes);CalendarRecord match=null;List<CalendarRecord> records=readCalendar(snapshot.sessionKey);
        for(CalendarRecord record:records)if(MessageDigest.isEqual(record.meetingHash,fingerprint)){match=record;break;}
        // Older clients do not know the sidecar. Their normal save leaves the
        // immediate prior file in .backup; use that exact verified ancestor to
        // retain settings by stable task ID, with changed due dates marked for review.
        if(match==null&&!snapshot.recoveredFromBackup) {
            Path backup=path(snapshot.sessionKey,".backup");
            if(Files.exists(backup))try {
                Snapshot prior=read(backup,snapshot.sessionKey,false);
                if(prior.revision!=Long.MAX_VALUE&&prior.revision+1==snapshot.revision) {
                    byte[] priorHash=digest().digest(Files.readAllBytes(backup));
                    for(CalendarRecord record:records)if(MessageDigest.isEqual(record.meetingHash,priorHash)){match=record;break;}
                }
            } catch(IOException ignored) { /* the current valid meeting remains readable */ }
        }
        if(match==null&&!records.isEmpty()) {
            // Several edits in an older client may replace the immediate
            // ancestor. Recover matching IDs for explicit review only; never
            // silently export a possibly stale choice.
            java.util.Map<String,CalendarSettings> recovered=new java.util.HashMap<>();
            for(Task task:snapshot.tasks)for(CalendarRecord record:records){
                CalendarSettings value=record.values.get(task.id);
                if(value!=null){recovered.put(task.id,value.forReview());break;}
            }
            if(!recovered.isEmpty())match=new CalendarRecord(fingerprint,recovered);
        }
        if(match==null)return snapshot;
        List<Task> tasks=new ArrayList<>();
        for(Task task:snapshot.tasks)tasks.add(new Task(task.id,task.text,task.owner,task.due,task.completed,match.values.get(task.id),true));
        return new Snapshot(snapshot.sessionKey,snapshot.revision,snapshot.transcript,snapshot.notes,tasks,snapshot.recoveredFromBackup);
    }
    private void writeCalendar(String key,Snapshot value,byte[] meeting)throws IOException {
        List<CalendarRecord> old=readCalendar(key),records=new ArrayList<>();byte[] fingerprint=digest().digest(meeting);
        java.util.Map<String,CalendarSettings> settings=new java.util.LinkedHashMap<>();
        for(Task task:value.tasks)if(task.calendar!=null)settings.put(task.id,task.calendar);
        records.add(new CalendarRecord(fingerprint,settings));
        // Preserve the exact current and backup versions even after repeated
        // interrupted saves; failed attempts must not evict the good backup.
        for(String extension:new String[]{".meeting",".backup"}) {
            Path existing=path(key,extension);if(!Files.exists(existing))continue;
            long size=Files.size(existing);if(size<36||size>MAX_BYTES)continue;
            byte[] bytes=Files.readAllBytes(existing);if(bytes.length!=size)throw new IOException("saved meeting changed while preparing calendar choices");
            byte[] existingHash=digest().digest(bytes);
            if(records.stream().anyMatch(record->MessageDigest.isEqual(record.meetingHash,existingHash)))continue;
            for(CalendarRecord record:old)if(MessageDigest.isEqual(record.meetingHash,existingHash)){records.add(record);break;}
        }
        for(CalendarRecord record:old) {
            if(records.size()==3)break;
            if(records.stream().noneMatch(item->MessageDigest.isEqual(item.meetingHash,record.meetingHash)))records.add(record);
        }
        LimitedOutput limited=new LimitedOutput();ByteArrayOutputStream buffer=limited.buffer;DataOutputStream out=new DataOutputStream(limited);
        out.writeInt(0x43435332);string(out,key);out.writeInt(records.size());
        for(CalendarRecord record:records){out.write(record.meetingHash);out.writeInt(record.values.size());
            for(java.util.Map.Entry<String,CalendarSettings> entry:record.values.entrySet()){
                CalendarSettings c=entry.getValue();string(out,entry.getKey());out.writeInt(c.reminderMinutes==null?-1:c.reminderMinutes);
                string(out,c.reminderAt);string(out,c.slotStart);string(out,c.slotEnd);string(out,c.selectedForDue);out.writeBoolean(c.recoveredForReview);
            }
        }
        out.flush();byte[] body=buffer.toByteArray();buffer.write(digest().digest(body));
        Path temp=Files.createTempFile(directory,".calendar-",".tmp");
        try{writeDurable(temp,buffer.toByteArray());Files.move(temp,path(key,".calendar"),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
        finally{Files.deleteIfExists(temp);}
    }
}
