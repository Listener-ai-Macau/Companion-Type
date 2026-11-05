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
    /** Approximate position of one recognizer window, not a word-level timestamp. */
    public static final class TranscriptWindow {
        public final String text;
        public final long startMs,endMs;
        public TranscriptWindow(String text,long startMs,long endMs) {
            if(text==null||text.isEmpty()||startMs<0||endMs<=startMs)throw new IllegalArgumentException("invalid transcript window");
            this.text=text;this.startMs=startMs;this.endMs=endMs;
        }
    }
    public static final class TranscriptTiming {
        public final long durationMs;
        public final List<TranscriptWindow> windows;
        /** Null means no recognition-coverage metadata was saved; an empty list means none was reported. */
        public final List<UnrecognizedRange> unrecognized;
        private TranscriptTiming(long durationMs,List<TranscriptWindow> windows,List<UnrecognizedRange> unrecognized) {
            this.durationMs=durationMs;this.windows=Collections.unmodifiableList(new ArrayList<>(windows));
            this.unrecognized=unrecognized==null?null:Collections.unmodifiableList(new ArrayList<>(unrecognized));
        }
    }
    /** An audio interval with no recognized text: it may be quiet or contain missed speech. */
    public static final class UnrecognizedRange {
        public final long startMs,endMs;
        public UnrecognizedRange(long startMs,long endMs) {
            if(startMs<0||endMs<=startMs)throw new IllegalArgumentException("invalid unrecognized range");
            this.startMs=startMs;this.endMs=endMs;
        }
    }
    /** Saved AI result, separate from the user's notes and confirmed tasks. */
    public static final class Minutes {
        public final String sessionKey,json,historyId;
        public final long revision,sourceMeetingRevision;
        /** The saved transcript has changed, or is unavailable; review before reuse. */
        public final boolean sourceChanged,sourceMissing,recoveredFromBackup;
        private final byte[] sourceHash;
        private Minutes(String key,String json,long revision,long sourceRevision,boolean changed,boolean missing,boolean recovered,byte[] sourceHash,String historyId) {
            this.sessionKey=key;this.json=json;this.revision=revision;sourceMeetingRevision=sourceRevision;
            sourceChanged=changed;sourceMissing=missing;recoveredFromBackup=recovered;this.sourceHash=sourceHash.clone();this.historyId=historyId;
        }
    }
    /** Previous results remain available even when a newer result is generated. */
    public static final class MinutesHistory {
        public final List<Minutes> versions;
        public final int unreadableFiles;
        private MinutesHistory(List<Minutes> versions,int unreadableFiles) {
            this.versions=Collections.unmodifiableList(new ArrayList<>(versions));this.unreadableFiles=unreadableFiles;
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
    /** Reopen the last saved AI result, even if its source transcript has changed. */
    public Minutes loadMinutes(String key) throws IOException {
        return locked(key,()->{
            Snapshot meeting;
            try{meeting=loadLocked(key);}catch(IOException error){meeting=null;}
            return loadMinutesLocked(key,meeting);
        });
    }
    /** List older saved results, newest first; damaged versions do not hide the others. */
    public MinutesHistory listMinutesHistory(String key)throws IOException {
        return locked(key,()->{
            Snapshot meeting;try{meeting=loadLocked(key);}catch(IOException error){meeting=null;}
            String prefix=path(key,".minutes-history-").getFileName().toString();
            List<Minutes> versions=new ArrayList<>();int unreadable=0;
            try(DirectoryStream<Path> files=Files.newDirectoryStream(directory,prefix+"*.bin")){
                for(Path file:files){
                    try {
                        Minutes item=readMinutes(file,key,meeting,false);
                        byte[] bytes=Files.readAllBytes(file);
                        String expected=prefix+item.revision+"-"+hex(digest().digest(bytes))+".bin";
                        if(!file.getFileName().toString().equals(expected))throw new IOException("minutes history identity mismatch");
                        versions.add(item);
                    }catch(IOException error){unreadable++;}
                }
            }
            versions.sort((a,b)->Long.compare(b.revision,a.revision));
            return new MinutesHistory(versions,unreadable);
        });
    }
    /**
     * Save a generated or edited result for the transcript actually sent to AI.
     * Both revisions are obtained before generation; 0 means no saved minutes.
     * A conflict leaves both the meeting and the prior result untouched.
     */
    public Minutes saveMinutes(String key,long expectedMeetingRevision,long expectedMinutesRevision,
                               String sourceTranscript,String minutesJson) throws IOException {
        if(expectedMeetingRevision<=0||expectedMinutesRevision<0||sourceTranscript==null||minutesJson==null||minutesJson.trim().isEmpty())
            throw new IllegalArgumentException("meeting, source text and minutes required");
        return locked(key,()->{
            Snapshot meeting=loadLocked(key);
            if(meeting==null||meeting.revision!=expectedMeetingRevision||!meeting.transcript.equals(sourceTranscript))
                throw new IOException("meeting changed; reload before saving minutes");
            Minutes previous=loadMinutesLocked(key,meeting);
            long revision=previous==null?0:previous.revision;
            if(revision!=expectedMinutesRevision)throw new IOException("minutes changed; reload before saving");
            byte[] sourceHash=digest().digest(sourceTranscript.getBytes(StandardCharsets.UTF_8));
            return persistMinutesLocked(key,meeting,previous,meeting.revision,sourceHash,minutesJson);
        });
    }
    /** Save a manual edit and retain its original source unless the user explicitly reviewed the current text. */
    public Minutes saveEditedMinutes(String key,long expectedMeetingRevision,long expectedMinutesRevision,
                                     String expectedMinutesJson,String editedMinutesJson,boolean reviewedCurrentSource)throws IOException {
        if(expectedMeetingRevision<=0||expectedMinutesRevision<=0||expectedMinutesJson==null||editedMinutesJson==null||editedMinutesJson.trim().isEmpty())
            throw new IllegalArgumentException("meeting, existing minutes and edited content required");
        return locked(key,()->{
            Snapshot meeting=loadLocked(key);
            if(meeting==null||meeting.revision!=expectedMeetingRevision)throw new IOException("meeting changed; reload before editing minutes");
            Minutes previous=loadMinutesLocked(key,meeting);
            if(previous==null||previous.revision!=expectedMinutesRevision||!previous.json.equals(expectedMinutesJson))
                throw new IOException("minutes changed; reload before editing");
            if(!reviewedCurrentSource&&editedMinutesJson.equals(previous.json))return previous;
            long sourceRevision=reviewedCurrentSource?meeting.revision:previous.sourceMeetingRevision;
            byte[] sourceHash=reviewedCurrentSource?digest().digest(meeting.transcript.getBytes(StandardCharsets.UTF_8)):previous.sourceHash;
            return persistMinutesLocked(key,meeting,previous,sourceRevision,sourceHash,editedMinutesJson);
        });
    }
    /** Restore one saved version without relabeling its original transcript. */
    public Minutes restoreMinutesHistory(String key,long expectedMeetingRevision,long expectedMinutesRevision,String historyId)throws IOException {
        if(expectedMeetingRevision<=0||expectedMinutesRevision<0||historyId==null||!historyId.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("meeting and history identity required");
        return locked(key,()->{
            Snapshot meeting=loadLocked(key);
            if(meeting==null||meeting.revision!=expectedMeetingRevision)throw new IOException("meeting changed; reload before restoring minutes");
            Minutes previous=loadMinutesLocked(key,meeting);
            if((previous==null?0:previous.revision)!=expectedMinutesRevision)throw new IOException("minutes changed; reload before restoring");
            String prefix=path(key,".minutes-history-").getFileName().toString();Minutes selected=null;
            try(DirectoryStream<Path> files=Files.newDirectoryStream(directory,prefix+"*-"+historyId+".bin")){
                for(Path file:files){
                    Minutes candidate=readMinutes(file,key,meeting,false);
                    if(!historyId.equals(candidate.historyId)||!file.getFileName().toString().equals(prefix+candidate.revision+"-"+candidate.historyId+".bin"))throw new IOException("minutes history identity mismatch");
                    if(selected!=null)throw new IOException("ambiguous minutes history");selected=candidate;
                }
            }
            if(selected==null)throw new IOException("minutes history is no longer available");
            return persistMinutesLocked(key,meeting,previous,selected.sourceMeetingRevision,selected.sourceHash,selected.json);
        });
    }
    private Minutes persistMinutesLocked(String key,Snapshot meeting,Minutes previous,long sourceRevision,byte[] sourceHash,String minutesJson)throws IOException {
        long revision=previous==null?0:previous.revision;
        if(revision==Long.MAX_VALUE)throw new IOException("minutes revision limit reached");
        byte[] bytes=encodeMinutes(key,revision+1,sourceRevision,sourceHash,minutesJson);
        Path current=path(key,".minutes"),backup=path(key,".minutes-backup");
        Path temp=Files.createTempFile(directory,".minutes-",".tmp");
        try {
            writeDurable(temp,bytes);
            if(previous!=null) {
                Path prior=previous.recoveredFromBackup?backup:current;
                byte[] old=Files.readAllBytes(prior);
                Path archive=path(key,".minutes-history-"+previous.revision+"-"+hex(digest().digest(old))+".bin");
                if(Files.exists(archive)) {
                    if(!java.util.Arrays.equals(old,Files.readAllBytes(archive)))throw new IOException("minutes history conflict; saved result retained");
                } else {
                    Path historyTemp=Files.createTempFile(directory,".minutes-history-",".tmp");
                    try{writeDurable(historyTemp,old);Files.move(historyTemp,archive,StandardCopyOption.ATOMIC_MOVE);}
                    finally{Files.deleteIfExists(historyTemp);}
                }
            }
            if(previous!=null&&!previous.recoveredFromBackup) {
                Path backupTemp=Files.createTempFile(directory,".minutes-backup-",".tmp");
                try{writeDurable(backupTemp,Files.readAllBytes(current));Files.move(backupTemp,backup,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
                finally{Files.deleteIfExists(backupTemp);}
            } else if(previous!=null&&Files.exists(current)) {
                Files.move(current,path(key,".minutes-damaged-"+UUID.randomUUID()+".bin"),StandardCopyOption.ATOMIC_MOVE);
            }
            Files.move(temp,current,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            return readMinutes(current,key,meeting,false);
        } finally {Files.deleteIfExists(temp);}
    }
    /** Explicitly delete only this meeting's saved AI results and their backups. */
    public int deleteMinutes(String key)throws IOException {
        return locked(key,()->{
            int removed=0;
            if(Files.deleteIfExists(path(key,".minutes")))removed++;
            if(Files.deleteIfExists(path(key,".minutes-backup")))removed++;
            String historyPrefix=path(key,".minutes-history-").getFileName().toString();
            try(DirectoryStream<Path> files=Files.newDirectoryStream(directory,historyPrefix+"*.bin")) {
                for(Path file:files) {
                    String name=file.getFileName().toString();
                    String suffix=name.substring(historyPrefix.length(),name.length()-4);
                    if(!suffix.matches("[1-9][0-9]*-[0-9a-f]{64}"))continue;
                    if(Files.deleteIfExists(file))removed++;
                }
            }
            String prefix=path(key,".minutes-damaged-").getFileName().toString();
            try(DirectoryStream<Path> files=Files.newDirectoryStream(directory,prefix+"*.bin")) {
                for(Path file:files) {
                    String name=file.getFileName().toString(),id=name.substring(prefix.length(),name.length()-4);
                    try {
                        if(!UUID.fromString(id).toString().equals(id))continue;
                    } catch(IllegalArgumentException invalid){continue;}
                    if(Files.deleteIfExists(file))removed++;
                }
            }
            return removed;
        });
    }
    private Minutes loadMinutesLocked(String key,Snapshot meeting)throws IOException {
        Path current=path(key,".minutes"),backup=path(key,".minutes-backup");IOException mainError=null;
        if(Files.exists(current))try{return readMinutes(current,key,meeting,false);}catch(IOException error){mainError=error;}
        if(Files.exists(backup))try{return readMinutes(backup,key,meeting,true);}catch(IOException error){if(mainError!=null)error.addSuppressed(mainError);throw error;}
        if(mainError!=null)throw mainError;
        return null;
    }
    private static byte[] encodeMinutes(String key,long revision,long sourceRevision,byte[] sourceHash,String json)throws IOException {
        LimitedOutput limited=new LimitedOutput();ByteArrayOutputStream buffer=limited.buffer;DataOutputStream out=new DataOutputStream(limited);
        out.writeInt(0x434d4e31);string(out,key);out.writeLong(revision);out.writeLong(sourceRevision);out.write(sourceHash);string(out,json);
        out.flush();byte[] body=buffer.toByteArray();buffer.write(digest().digest(body));return buffer.toByteArray();
    }
    private static Minutes readMinutes(Path path,String key,Snapshot meeting,boolean recovered)throws IOException {
        long size=Files.size(path);if(size<88||size>MAX_BYTES)throw new IOException("saved minutes are damaged");
        byte[] bytes=Files.readAllBytes(path);if(bytes.length!=size)throw new IOException("saved minutes changed while reading");
        int n=bytes.length-32;MessageDigest hash=digest();hash.update(bytes,0,n);
        if(!MessageDigest.isEqual(hash.digest(),java.util.Arrays.copyOfRange(bytes,n,bytes.length)))throw new IOException("saved minutes are damaged");
        DataInputStream in=new DataInputStream(new ByteArrayInputStream(bytes,0,n));
        if(in.readInt()!=0x434d4e31)throw new IOException("unsupported minutes format");
        String savedKey=string(in);long revision=in.readLong(),sourceRevision=in.readLong();byte[] sourceHash=new byte[32];in.readFully(sourceHash);String json=string(in);
        if(!key.equals(savedKey)||revision<=0||sourceRevision<=0||json==null||json.trim().isEmpty()||in.available()!=0)
            throw new IOException("invalid saved minutes");
        boolean missing=meeting==null;
        boolean changed=missing||!MessageDigest.isEqual(sourceHash,digest().digest(meeting.transcript.getBytes(StandardCharsets.UTF_8)));
        return new Minutes(savedKey,json,revision,sourceRevision,changed,missing,recovered,sourceHash,hex(digest().digest(bytes)));
    }
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
    /**
     * Save a recognition result without replacing notes, tasks or calendar choices.
     * expectedTranscript is the saved text observed before recognition, or null
     * if the meeting did not exist. Keep the result and retry after a conflict.
     */
    public Snapshot saveTranscription(String key,String expectedTranscript,String recognizedText)throws IOException {
        if(recognizedText==null)throw new IllegalArgumentException("recognized text required");
        Snapshot previous=load(key);
        if(previous!=null&&previous.transcript.equals(recognizedText))return previous;
        if(previous==null) {
            if(expectedTranscript!=null)throw new IOException("meeting changed; review transcription before saving");
            return save(key,0,recognizedText,"",Collections.emptyList());
        }
        if(!previous.transcript.equals(expectedTranscript))throw new IOException("transcript changed; review transcription before saving");
        return save(key,previous.revision,recognizedText,previous.notes,previous.tasks);
    }
    /**
     * Save a user correction while retaining the text that was present before
     * the first correction through this API. Existing generic saves and ASR
     * retries keep their current behavior; use this only for an explicit edit.
     * The returned revision can be used for the next edit or minutes save.
     */
    public Snapshot saveTranscriptCorrection(String key,long expectedRevision,String correctedText)throws IOException {
        if(correctedText==null||expectedRevision<=0)throw new IllegalArgumentException("text and meeting revision required");
        Snapshot previous=load(key);
        if(previous==null||previous.revision!=expectedRevision)throw new IOException("meeting changed; reload before saving");
        if(previous.transcript.equals(correctedText))return previous;
        return saveInternal(key,expectedRevision,correctedText,previous.notes,previous.tasks,true);
    }
    /** The text saved before the first explicit correction, or null if none was retained. */
    public String loadTranscriptBeforeCorrection(String key)throws IOException {
        return locked(key,()->{
            Path saved=path(key,".transcript-before-correction");
            return Files.exists(saved)?read(saved,key,false).transcript:null;
        });
    }
    /** Delete only the retained pre-correction text when explicitly requested by the user. */
    public boolean deleteTranscriptBeforeCorrection(String key)throws IOException {
        return locked(key,()->Files.deleteIfExists(path(key,".transcript-before-correction")));
    }
    private void retainTranscriptBeforeCorrection(String key,Snapshot previous)throws IOException {
        Path saved=path(key,".transcript-before-correction");
        if(Files.exists(saved)){read(saved,key,false);return;}
        // The existing verified meeting format gives the retained text an
        // identity and checksum without copying the user's notes or tasks.
        Snapshot textOnly=new Snapshot(key,previous.revision,previous.transcript,"",Collections.emptyList(),false);
        Path temp=Files.createTempFile(directory,".transcript-before-correction-",".tmp");
        try{writeDurable(temp,encode(textOnly));Files.move(temp,saved,StandardCopyOption.ATOMIC_MOVE);}
        finally{Files.deleteIfExists(temp);}
    }
    /**
     * Save the window positions returned by local recognition, after saving its exact text.
     * The WAV must be the unchanged file used for that recognition. Positions are bound to
     * both its contents and the saved transcript; edited text/audio will not seek incorrectly.
     * Run on a worker thread because hashing a long recording reads the entire file.
     */
    public void saveTranscriptTiming(String key,String sourceTranscript,Path wav,long durationMs,List<TranscriptWindow> windows)throws IOException {
        saveTranscriptTiming(key,sourceTranscript,wav,durationMs,windows,null);
    }
    public void saveTranscriptTiming(String key,String sourceTranscript,Path wav,long durationMs,List<TranscriptWindow> windows,List<UnrecognizedRange> unrecognized)throws IOException {
        if(sourceTranscript==null||wav==null||durationMs<0||windows==null)throw new IllegalArgumentException("source text, WAV, duration and windows required");
        saveTranscriptTimingIdentity(key,sourceTranscript,hashFile(wav),durationMs,windows,unrecognized);
    }
    /** Save positions for the complete verified decoded part set of one recording. */
    public void saveTranscriptTimingParts(String key,String sourceTranscript,RecordingLibrary.Session session,Path partsDirectory,long durationMs,List<TranscriptWindow> windows)throws IOException {
        saveTranscriptTimingParts(key,sourceTranscript,session,partsDirectory,durationMs,windows,null);
    }
    public void saveTranscriptTimingParts(String key,String sourceTranscript,RecordingLibrary.Session session,Path partsDirectory,long durationMs,List<TranscriptWindow> windows,List<UnrecognizedRange> unrecognized)throws IOException {
        if(sourceTranscript==null||session==null||partsDirectory==null||durationMs<0||windows==null)
            throw new IllegalArgumentException("source text, recording, parts, duration and windows required");
        PartsIdentity identity=partsIdentity(session,partsDirectory);
        if(identity==null)throw new IOException("recording audio parts are unavailable; original retained");
        if(identity.durationMs!=durationMs)throw new IOException("transcript duration does not match recording parts");
        // Keep the existing timing-file format: older builds safely treat the
        // domain-separated parts identity as a nonmatching single WAV.
        saveTranscriptTimingIdentity(key,sourceTranscript,identity.hash,durationMs,windows,unrecognized);
    }
    private void saveTranscriptTimingIdentity(String key,String sourceTranscript,byte[] audioHash,long durationMs,List<TranscriptWindow> windows,List<UnrecognizedRange> unrecognized)throws IOException {
        List<TranscriptWindow> copy=new ArrayList<>(windows);
        List<UnrecognizedRange> gaps=unrecognized==null?null:new ArrayList<>(unrecognized);
        validateTiming(sourceTranscript,durationMs,copy);
        validateUnrecognized(durationMs,gaps);
        locked(key,()->{
            Snapshot meeting=loadLocked(key);
            if(meeting==null||!meeting.transcript.equals(sourceTranscript))throw new IOException("transcript changed; reload before saving timing");
            LimitedOutput limited=new LimitedOutput();DataOutputStream out=new DataOutputStream(limited);
            out.writeInt(0x43545431);string(out,key);out.write(digest().digest(sourceTranscript.getBytes(StandardCharsets.UTF_8)));
            out.write(audioHash);out.writeLong(durationMs);out.writeInt(copy.size());
            int offset=0;
            for(TranscriptWindow window:copy) {
                out.writeInt(offset);offset+=window.text.length();out.writeInt(offset);
                out.writeLong(window.startMs);out.writeLong(window.endMs);offset++;
            }
            out.flush();byte[] body=limited.buffer.toByteArray();limited.buffer.write(digest().digest(body));
            Path temp=Files.createTempFile(directory,".timing-",".tmp");
            try{
                byte[] timing=limited.buffer.toByteArray();
                writeDurable(temp,timing);
                Files.deleteIfExists(path(key,".timing-gaps"));
                Files.move(temp,path(key,".timing"),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
                if(gaps!=null)writeUnrecognized(key,timing,gaps);
            }
            finally{Files.deleteIfExists(temp);}
            return null;
        });
    }
    /** Return null if no timing exists or the transcript/audio has since changed. */
    public TranscriptTiming loadTranscriptTiming(String key,Path wav)throws IOException {
        if(wav==null)throw new IllegalArgumentException("WAV required");
        return loadTranscriptTimingIdentity(key,()->Files.exists(wav)?hashFile(wav):null,false);
    }
    /** Reopen saved positions only while the same complete part set remains available. */
    public TranscriptTiming loadTranscriptTimingParts(String key,RecordingLibrary.Session session,Path partsDirectory)throws IOException {
        if(session==null||partsDirectory==null)throw new IllegalArgumentException("recording and parts required");
        return loadTranscriptTimingIdentity(key,()->{
            PartsIdentity identity=partsIdentity(session,partsDirectory);return identity==null?null:identity.hash;
        },false);
    }
    /** Approximate positions for the retained pre-correction text, when its existing timing and audio still match. */
    public TranscriptTiming loadTranscriptBeforeCorrectionTiming(String key,Path wav)throws IOException {
        if(wav==null)throw new IllegalArgumentException("WAV required");
        return loadTranscriptTimingIdentity(key,()->Files.exists(wav)?hashFile(wav):null,true);
    }
    /** As above, for a complete verified set of decoded recording parts. */
    public TranscriptTiming loadTranscriptBeforeCorrectionTimingParts(String key,RecordingLibrary.Session session,Path partsDirectory)throws IOException {
        if(session==null||partsDirectory==null)throw new IllegalArgumentException("recording and parts required");
        return loadTranscriptTimingIdentity(key,()->{
            PartsIdentity identity=partsIdentity(session,partsDirectory);return identity==null?null:identity.hash;
        },true);
    }
    private interface TimingIdentity {byte[] read()throws IOException;}
    private static final class PartsIdentity {
        final byte[] hash;final long durationMs;
        PartsIdentity(byte[] hash,long durationMs){this.hash=hash;this.durationMs=durationMs;}
    }
    private static PartsIdentity partsIdentity(RecordingLibrary.Session session,Path directory)throws IOException {
        Path root=directory.toAbsolutePath();Path receipt=root.resolve(".companion-parts");
        if(!Files.exists(receipt))return null;
        if(!Files.isRegularFile(receipt,java.nio.file.LinkOption.NOFOLLOW_LINKS))throw new IOException("audio parts receipt unavailable");
        byte[] before=hashFile(receipt);
        NativeAudio.PartsResult parts=NativeAudio.loadParts(session,root);
        if(parts==null)return null;
        byte[] after=hashFile(receipt);
        if(!MessageDigest.isEqual(before,after))throw new IOException("recording audio parts changed; retry");
        MessageDigest hash=digest();hash.update("companion-transcript-parts-v1\0".getBytes(StandardCharsets.UTF_8));hash.update(after);
        // Recognition rounds the final partial millisecond up so that its last
        // time window remains inside the reported duration. Use the same rule.
        return new PartsIdentity(hash.digest(),parts.samples/16+(parts.samples%16==0?0:1));
    }
    private TranscriptTiming loadTranscriptTimingIdentity(String key,TimingIdentity identity,boolean beforeCorrection)throws IOException {
        return locked(key,()->{
            Path saved=path(key,".timing");if(!Files.exists(saved))return null;
            Snapshot meeting;
            if(beforeCorrection) {
                Path original=path(key,".transcript-before-correction");
                meeting=Files.exists(original)?read(original,key,false):null;
            } else meeting=loadLocked(key);
            if(meeting==null)return null;
            long size=Files.size(saved);if(size<116||size>MAX_BYTES)throw new IOException("saved transcript timing is damaged");
            byte[] bytes=Files.readAllBytes(saved);if(bytes.length!=size)throw new IOException("saved transcript timing changed while reading");
            int n=bytes.length-32;MessageDigest check=digest();check.update(bytes,0,n);
            if(!MessageDigest.isEqual(check.digest(),java.util.Arrays.copyOfRange(bytes,n,bytes.length)))throw new IOException("saved transcript timing is damaged");
            DataInputStream in=new DataInputStream(new ByteArrayInputStream(bytes,0,n));
            if(in.readInt()!=0x43545431||!key.equals(string(in)))throw new IOException("invalid saved transcript timing");
            byte[] textHash=new byte[32],audioHash=new byte[32];in.readFully(textHash);in.readFully(audioHash);
            if(!MessageDigest.isEqual(textHash,digest().digest(meeting.transcript.getBytes(StandardCharsets.UTF_8))))return null;
            byte[] actual=identity.read();
            if(actual==null||!MessageDigest.isEqual(audioHash,actual))return null;
            long duration=in.readLong();int count=in.readInt();
            if(duration<0||count<0||count>in.available()/24)throw new IOException("invalid saved transcript timing");
            List<TranscriptWindow> result=new ArrayList<>();int offset=0;long lastEnd=0;
            for(int i=0;i<count;i++) {
                int start=in.readInt(),end=in.readInt();long startMs=in.readLong(),endMs=in.readLong();
                if(start!=offset||end<=start||end>meeting.transcript.length()||startMs<0||(startMs<lastEnd&&lastEnd-startMs>1)||endMs<=startMs||endMs>duration)throw new IOException("invalid saved transcript timing");
                result.add(new TranscriptWindow(meeting.transcript.substring(start,end),startMs,endMs));lastEnd=endMs;offset=end;
                if(i+1<count){if(offset>=meeting.transcript.length()||meeting.transcript.charAt(offset)!='\n')throw new IOException("invalid saved transcript timing");offset++;}
            }
            if(offset!=meeting.transcript.length()||in.available()!=0)throw new IOException("invalid saved transcript timing");
            return new TranscriptTiming(duration,result,readUnrecognized(key,bytes,duration));
        });
    }
    /** Remove the position data along with the recording and meeting on user deletion. */
    public boolean deleteTranscriptTiming(String key)throws IOException {return locked(key,()->{boolean removed=Files.deleteIfExists(path(key,".timing"));Files.deleteIfExists(path(key,".timing-gaps"));return removed;});}
    private static void validateUnrecognized(long duration,List<UnrecognizedRange> ranges)throws IOException {
        if(ranges==null)return;
        long lastEnd=0;
        for(UnrecognizedRange range:ranges) {
            if(range==null||range.startMs<lastEnd||range.endMs>duration)throw new IOException("invalid unrecognized ranges");
            lastEnd=range.endMs;
        }
    }
    private void writeUnrecognized(String key,byte[] timing,List<UnrecognizedRange> ranges)throws IOException {
        LimitedOutput limited=new LimitedOutput();DataOutputStream out=new DataOutputStream(limited);
        out.writeInt(0x43544731);out.write(digest().digest(timing));out.writeInt(ranges.size());
        for(UnrecognizedRange range:ranges){out.writeLong(range.startMs);out.writeLong(range.endMs);}
        out.flush();byte[] body=limited.buffer.toByteArray();limited.buffer.write(digest().digest(body));
        Path temp=Files.createTempFile(directory,".timing-gaps-",".tmp");
        try{writeDurable(temp,limited.buffer.toByteArray());Files.move(temp,path(key,".timing-gaps"),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
        finally{Files.deleteIfExists(temp);}
    }
    private List<UnrecognizedRange> readUnrecognized(String key,byte[] timing,long duration)throws IOException {
        Path saved=path(key,".timing-gaps");if(!Files.exists(saved))return null;
        long size=Files.size(saved);if(size<72||size>MAX_BYTES)return null;
        byte[] bytes=Files.readAllBytes(saved);if(bytes.length!=size)return null;
        int n=bytes.length-32;MessageDigest check=digest();check.update(bytes,0,n);
        if(!MessageDigest.isEqual(check.digest(),java.util.Arrays.copyOfRange(bytes,n,bytes.length)))return null;
        DataInputStream in=new DataInputStream(new ByteArrayInputStream(bytes,0,n));
        if(in.readInt()!=0x43544731)return null;
        byte[] timingHash=new byte[32];in.readFully(timingHash);
        if(!MessageDigest.isEqual(timingHash,digest().digest(timing)))return null;
        int count=in.readInt();if(count<0||count!=in.available()/16||in.available()%16!=0)return null;
        List<UnrecognizedRange> result=new ArrayList<>();
        try{for(int i=0;i<count;i++)result.add(new UnrecognizedRange(in.readLong(),in.readLong()));validateUnrecognized(duration,result);}
        catch(IllegalArgumentException|IOException invalid){return null;}
        return result;
    }
    private static void validateTiming(String transcript,long duration,List<TranscriptWindow> windows)throws IOException {
        StringBuilder joined=new StringBuilder();long lastEnd=0;
        for(TranscriptWindow window:windows) {
            // Adjacent sample boundaries can overlap by 1 ms after rounding.
            if(window==null||(window.startMs<lastEnd&&lastEnd-window.startMs>1)||window.endMs>duration)throw new IOException("invalid transcript window positions");
            if(joined.length()>0)joined.append('\n');joined.append(window.text);lastEnd=window.endMs;
        }
        if(!joined.toString().equals(transcript))throw new IOException("transcript windows do not match saved text");
    }
    private static byte[] hashFile(Path path)throws IOException {
        MessageDigest hash=digest();byte[] buffer=new byte[64*1024];
        try(java.io.InputStream input=Files.newInputStream(path)){for(int n;(n=input.read(buffer))!=-1;)hash.update(buffer,0,n);}
        return hash.digest();
    }
    /** Revision 0 creates a new meeting. A stale revision leaves the saved content untouched. */
    public Snapshot save(String key,long expectedRevision,String transcript,String notes,List<Task> tasks) throws IOException {
        return saveInternal(key,expectedRevision,transcript,notes,tasks,false);
    }
    private Snapshot saveInternal(String key,long expectedRevision,String transcript,String notes,List<Task> tasks,boolean retainTranscript) throws IOException {
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
                if(retainTranscript&&previous!=null&&!previous.transcript.equals(transcript))retainTranscriptBeforeCorrection(key,previous);
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
