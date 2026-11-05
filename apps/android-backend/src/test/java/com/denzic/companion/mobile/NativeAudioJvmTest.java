package com.denzic.companion.mobile;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.zip.CRC32;
import java.io.ByteArrayOutputStream;
import java.util.UUID;

/** JVM-to-native bridge test with synthetic silent Opus, no Android device. */
public final class NativeAudioJvmTest {
    private static void put16(byte[] p,int i,int v){p[i]=(byte)v;p[i+1]=(byte)(v>>>8);}
    private static void put32(byte[] p,int i,long v){for(int n=0;n<4;n++)p[i+n]=(byte)(v>>>(8*n));}
    private static void put64(byte[] p,int i,long v){for(int n=0;n<8;n++)p[i+n]=(byte)(v>>>(8*n));}
    private static byte[] packet(byte[] raw,byte[] hash,int offset,int length,int sequence,boolean last) {
        int header=last?56:24;byte[] p=new byte[header+length];p[0]=1;p[1]=(byte)(last?1:0);put16(p,2,length);
        put32(p,4,41);put32(p,8,sequence);put32(p,12,offset);put32(p,16,raw.length);
        if(last)System.arraycopy(hash,0,p,24,32);System.arraycopy(raw,offset,p,header,length);
        CRC32 crc=new CRC32();crc.update(p,4,16);crc.update(raw,offset,length);put32(p,20,crc.getValue());return p;
    }
    private static final class ReceiptLink implements RecordingClient.Link {
        byte[] receipt;int writes;
        public int mtu(){return 247;}public byte[] read(UUID id){throw new AssertionError();}
        public void subscribe(UUID id){if(!id.equals(RecordingClient.RECORDING_CONSUME))throw new AssertionError();}
        public void write(UUID id,byte[] value){writes++;receipt=value.clone();}
        public byte[] await(UUID id,long timeout){return receipt.clone();}
        public void close(){}
    }
    public static void main(String[] args)throws Exception {
        if(args.length==3 && args[0].equals("--abandon-managed-audio")) {
            Path root=Paths.get(args[1]),cache=Paths.get(args[2]);
            RecordingLibrary.Session session=RecordingLibrary.sessions(root).stream().filter(x->x.state==RecordingLibrary.SessionState.COMPLETE).findFirst().get();
            Path attempt=Files.createDirectory(cache.resolve("attempt-"+UUID.randomUUID()));
            ByteArrayOutputStream marker=new ByteArrayOutputStream();marker.write("Companion decoded audio v1\n".getBytes(java.nio.charset.StandardCharsets.UTF_8));marker.write(DeviceBookmarkCache.fingerprint(session));
            Files.write(attempt.resolve(".companion-decode-owner"),marker.toByteArray());
            Path parts=Files.createDirectory(attempt.resolve("parts"));Files.write(parts.resolve("part-00000000.wav"),new byte[]{1,2,3});
            Runtime.getRuntime().halt(19);
        }
        Path root=Files.createTempDirectory(Paths.get(args[0]),"jni-silence-");
        ByteArrayOutputStream source=new ByteArrayOutputStream();source.write(new byte[]{'C','O','P','1',3,1,20,3,(byte)128,62,0,0});
        int[] opus={184,91,61,13,6,212,119,103,154,112,59,167,214,84,199,215,224,197,21,15,83,26,25,151,74,91,44,201,192,179,8,78,13,165,128,204,28,243,127,83};
        byte[] audio=new byte[42];audio[0]=40;for(int i=0;i<opus.length;i++)audio[i+2]=(byte)opus[i];source.write(audio);source.write(audio);
        while(source.size()%248!=0)source.write(255);byte[] mark=new byte[32];System.arraycopy(new byte[]{'C','P','G','1'},0,mark,2,4);
        mark[6]=4;put32(mark,8,1);put64(mark,12,640);put64(mark,20,40);CRC32 markCrc=new CRC32();markCrc.update(mark,0,28);put32(mark,28,markCrc.getValue());
        source.write(mark);while(source.size()%248!=0)source.write(255);source.write(audio);byte[] raw=source.toByteArray();
        byte[] hash=MessageDigest.getInstance("SHA-256").digest(raw);CRC32 crc=new CRC32();crc.update(raw);
        byte[] d=new byte[112];System.arraycopy(new byte[]{'C','R','S','2'},0,d,0,4);put16(d,4,2);put16(d,6,112);put32(d,8,41);d[12]=1;d[20]=1;put32(d,40,960);put32(d,48,raw.length);put32(d,52,crc.getValue());System.arraycopy(hash,0,d,56,32);put32(d,88,1);d[92]=3;d[93]=3;d[96]=1;crc.reset();crc.update(d,0,108);put32(d,108,crc.getValue());
        RecorderWire.Descriptor descriptor=RecorderWire.Descriptor.decode(d);
        try(SegmentReceiver receiver=new SegmentReceiver(root,descriptor)){
            receiver.accept(packet(raw,hash,0,248,0,false));receiver.accept(packet(raw,hash,248,raw.length-248,1,true));receiver.finish();}
        RecordingLibrary.Session session=RecordingLibrary.sessions(root).get(0);Path wav=root.resolve("output.wav");
        NativeAudio.VerifiedPrefix ended=NativeAudio.inspectPrefix(session);
        if(!ended.captureComplete||ended.encodedSamples!=960||ended.bookmarks.size()!=1||ended.bookmarks.get(0).sourceSamples!=640)throw new AssertionError("complete prefix metadata mismatch");
        byte[] status=new byte[116];status[0]=1;put32(status,12,0x57424155L);System.arraycopy(d,96,status,20,12);
        System.arraycopy(new byte[]{'C','R','V','2'},0,status,84,4);put16(status,88,2);put16(status,90,32);put32(status,92,7);
        System.arraycopy(d,12,status,96,8);put16(status,104,64);put16(status,106,1024);put16(status,108,248);crc.reset();crc.update(status,84,28);put32(status,112,crc.getValue());
        ReceiptLink link=new ReceiptLink();int[] validated={0};
        DurableConsume consume=new DurableConsume(RecorderWire.Peer.fromStatus(status),link,dir->{},prefix->{
            NativeAudio.VerifiedPrefix checked=NativeAudio.inspectPrefix(prefix);
            if(checked.bookmarks.size()!=1||checked.bookmarks.get(0).sourceSamples!=640)throw new java.io.IOException("saved mark missing");validated[0]++;
        });
        if(!consume.consume(root,descriptor)||link.writes!=1||validated[0]!=1)throw new AssertionError("real JNI prefix was not verified before consume");
        if(!Arrays.equals(Files.readAllBytes(root.resolve(SegmentReceiver.key(descriptor)+".cop1")),raw))throw new AssertionError("original was changed by consumption");
        byte[] live=d.clone();live[20]=2;put32(live,88,0);live[92]=1;crc.reset();crc.update(live,0,108);put32(live,108,crc.getValue());
        RecorderWire.Descriptor liveDescriptor=RecorderWire.Descriptor.decode(live);String liveKey=SegmentReceiver.key(liveDescriptor);
        Files.write(root.resolve(liveKey+".meta"),live);Files.write(root.resolve(liveKey+".cop1"),raw);
        RecordingLibrary.Session incomplete=RecordingLibrary.sessions(root).stream().filter(x->x.state==RecordingLibrary.SessionState.INCOMPLETE).findFirst().get();
        NativeAudio.VerifiedPrefix prefix=NativeAudio.inspectPrefix(incomplete);
        if(prefix.captureComplete||prefix.encodedSamples!=960||prefix.bookmarks.size()!=1||prefix.bookmarks.get(0).elapsedMillis!=40)throw new AssertionError("open prefix metadata mismatch");
        NativeAudio.Result result=NativeAudio.decode(session,wav);byte[] output=Files.readAllBytes(wav);
        if(result.samples!=640||!result.captureComplete||output.length!=1324||!Arrays.equals(Arrays.copyOf(output,4),new byte[]{'R','I','F','F'}))throw new AssertionError("native output mismatch");
        if(result.bookmarks.size()!=1||result.bookmarks.get(0).sequence!=1||result.bookmarks.get(0).sourceSamples!=640||
            result.bookmarks.get(0).playbackSamples!=320||result.bookmarks.get(0).elapsedMillis!=40)throw new AssertionError("device bookmark was not preserved");
        Path partDir=root.resolve("split-output");NativeAudio.PartsResult split=NativeAudio.decodeParts(session,partDir);
        if(split.samples!=result.samples||!split.captureComplete||split.parts.size()!=1||split.bookmarks.size()!=1||split.bookmarks.get(0).playbackSamples!=320)
            throw new AssertionError("split decoder lost audio or mark");
        if(!Arrays.equals(Files.readAllBytes(split.parts.get(0).path),output))throw new AssertionError("split and single output differ");
        RecordingAudioRange.Result<byte[]> chosen=RecordingAudioRange.withRange(session,partDir,root.resolve("range-cache"),5,25,
            selected->Files.readAllBytes(selected));
        if(chosen.retainedTemporary!=null||chosen.value.length!=44+640||
            !Arrays.equals(Arrays.copyOfRange(chosen.value,44,chosen.value.length),Arrays.copyOfRange(output,44+160,44+800)))
            throw new AssertionError("public range API did not select the requested original samples");
        if(!Arrays.equals(Files.readAllBytes(split.parts.get(0).path),output))throw new AssertionError("range preview changed original");
        // A real recording need not end on a whole-millisecond sample. Native
        // recognition rounds up its duration and final window in that case.
        Path fractional=Files.createDirectory(root.resolve("fractional-output"));
        byte[] fractionalWav=Arrays.copyOf(output,output.length+2);
        put32(fractionalWav,4,fractionalWav.length-8);put32(fractionalWav,40,fractionalWav.length-44);
        Path fractionalFile=fractional.resolve("part-00000000.wav");Files.write(fractionalFile,fractionalWav);
        DecodedAudioParts.save(new NativeAudio.PartsResult(fractional,641,true,
            java.util.Collections.singletonList(new NativeAudio.Part(fractionalFile,0,641)),
            java.util.Collections.emptyList(),DeviceBookmarkCache.fingerprint(session)));
        MeetingStore fractionalStore=new MeetingStore(root.resolve("meeting-fractional"));
        fractionalStore.saveTranscription("fractional",null,"短句");
        java.util.List<MeetingStore.TranscriptWindow> fractionalWindows=java.util.Collections.singletonList(new MeetingStore.TranscriptWindow("短句",0,41));
        try{fractionalStore.saveTranscriptTimingParts("fractional","短句",session,fractional,40,fractionalWindows);throw new AssertionError("truncated duration accepted");}
        catch(java.io.IOException expected){}
        fractionalStore.saveTranscriptTimingParts("fractional","短句",session,fractional,41,fractionalWindows);
        MeetingStore.TranscriptTiming fractionalSaved=new MeetingStore(root.resolve("meeting-fractional")).loadTranscriptTimingParts("fractional",session,fractional);
        if(fractionalSaved==null||fractionalSaved.durationMs!=41||fractionalSaved.windows.get(0).endMs!=41)
            throw new AssertionError("fractional-millisecond transcript timing was not restored");
        NativeAudio.PartsResult splitAgain=NativeAudio.loadParts(session,partDir);
        if(splitAgain==null||splitAgain.samples!=640||splitAgain.parts.get(0).firstSample!=0||splitAgain.bookmarks.get(0).elapsedMillis!=40)
            throw new AssertionError("split receipt did not reopen");
        Path managed=Files.createDirectory(root.resolve("managed-parts"));
        Path unrelated=Files.createDirectory(managed.resolve("attempt-"+UUID.randomUUID()));
        Files.write(unrelated.resolve("user-file"),new byte[]{7});
        Path unknown=Files.createDirectory(managed.resolve("attempt-"+UUID.randomUUID()));
        ByteArrayOutputStream ownedMarker=new ByteArrayOutputStream();ownedMarker.write("Companion decoded audio v1\n".getBytes(java.nio.charset.StandardCharsets.UTF_8));ownedMarker.write(DeviceBookmarkCache.fingerprint(session));
        Files.write(unknown.resolve(".companion-decode-owner"),ownedMarker.toByteArray());
        Files.write(unknown.resolve("unexpected-file"),new byte[]{8});
        String javaExe=Paths.get(System.getProperty("java.home"),"bin","java").toString();
        Process abandoned=new ProcessBuilder(javaExe,"-cp",System.getProperty("java.class.path"),NativeAudioJvmTest.class.getName(),
            "--abandon-managed-audio",root.toString(),managed.toString()).inheritIO().start();
        if(abandoned.waitFor()!=19)throw new AssertionError("interruption fixture did not exit abruptly");
        NativeAudio.PartsResult managedResult=ManagedAudioParts.prepare(session,managed);
        if(managedResult.samples!=640||!Arrays.equals(Files.readAllBytes(managedResult.parts.get(0).path),output))
            throw new AssertionError("interrupted decode could not be retried");
        if(!Files.exists(unrelated.resolve("user-file")))throw new AssertionError("unrelated cache data was removed");
        if(!Files.exists(unknown.resolve("unexpected-file")))throw new AssertionError("unrecognized file in attempt was removed");
        try(java.util.stream.Stream<Path> entries=Files.list(managed)) {
            if(entries.filter(x->x.getFileName().toString().startsWith("attempt-")).count()!=3)throw new AssertionError("abandoned owned attempt was not cleaned");
        }
        try(java.io.RandomAccessFile file=new java.io.RandomAccessFile(managed.resolve(".companion-decode.lock").toFile(),"rw");
            java.nio.channels.FileLock lock=file.getChannel().lock()) {
            try{ManagedAudioParts.prepare(session,managed);throw new AssertionError("concurrent preparation accepted");}catch(java.io.IOException expected){}
            try{ManagedAudioParts.clear(session,managed);throw new AssertionError("concurrent cache clearing accepted");}catch(java.io.IOException expected){}
        }
        NativeAudio.PartsResult reused=ManagedAudioParts.prepare(session,managed);
        if(!reused.directory.equals(managedResult.directory))throw new AssertionError("completed audio was decoded again");
        byte[] damagedAudio=Files.readAllBytes(reused.parts.get(0).path);damagedAudio[damagedAudio.length-1]^=1;Files.write(reused.parts.get(0).path,damagedAudio);
        NativeAudio.PartsResult rebuilt=ManagedAudioParts.prepare(session,managed);
        if(rebuilt.directory.equals(reused.directory)||!Arrays.equals(Files.readAllBytes(rebuilt.parts.get(0).path),output)||!Files.exists(reused.parts.get(0).path))
            throw new AssertionError("damaged decoded copy was not retained and rebuilt");
        if(!Arrays.equals(Files.readAllBytes(root.resolve(SegmentReceiver.key(descriptor)+".cop1")),raw))throw new AssertionError("managed retry changed original");
        Path laterRoot=Files.createDirectory(root.resolve("later-copy"));byte[] laterDescriptor=d.clone();put32(laterDescriptor,8,42);
        crc.reset();crc.update(laterDescriptor,0,108);put32(laterDescriptor,108,crc.getValue());
        RecorderWire.Descriptor later=RecorderWire.Descriptor.decode(laterDescriptor);String laterKey=SegmentReceiver.key(later);
        Files.write(laterRoot.resolve(laterKey+".meta"),laterDescriptor);Files.write(laterRoot.resolve(laterKey+".cop1"),raw);
        RecordingLibrary.Session sameSessionNewSource=RecordingLibrary.sessions(laterRoot).get(0);
        NativeAudio.PartsResult laterAudio=ManagedAudioParts.prepare(sameSessionNewSource,managed);
        if(laterAudio.directory.equals(rebuilt.directory))throw new AssertionError("changed source reused old decoded data");
        Path otherAttempt=Files.createDirectory(managed.resolve("attempt-"+UUID.randomUUID()));
        ByteArrayOutputStream otherMarker=new ByteArrayOutputStream();otherMarker.write("Companion decoded audio v1\n".getBytes(java.nio.charset.StandardCharsets.UTF_8));otherMarker.write(DeviceBookmarkCache.fingerprint(incomplete));
        Files.write(otherAttempt.resolve(".companion-decode-owner"),otherMarker.toByteArray());
        Path otherParts=Files.createDirectory(otherAttempt.resolve("parts"));Files.write(otherParts.resolve("part-00000000.wav"),new byte[]{9});
        ManagedAudioParts.ClearResult cleared=ManagedAudioParts.clear(session,managed);
        if(cleared.removedAttempts!=3||cleared.retainedAttempts!=1||Files.exists(reused.directory)||Files.exists(rebuilt.directory)||Files.exists(laterAudio.directory))
            throw new AssertionError("selected recording cache was not cleared precisely");
        if(!Files.exists(otherParts.resolve("part-00000000.wav"))||!Files.exists(unrelated.resolve("user-file"))||!Files.exists(unknown.resolve("unexpected-file")))
            throw new AssertionError("another recording or unknown data was removed");
        if(!Arrays.equals(Files.readAllBytes(root.resolve(SegmentReceiver.key(descriptor)+".cop1")),raw))throw new AssertionError("cache clear changed original");
        ManagedAudioParts.ClearResult clearedAgain=ManagedAudioParts.clear(session,managed);
        if(clearedAgain.removedAttempts!=0||clearedAgain.retainedAttempts!=1)throw new AssertionError("repeat cache clear is not safe");
        if(ManagedAudioParts.prepare(session,managed).samples!=640)throw new AssertionError("original could not be decoded after cache clear");
        ManagedAudioParts.prepare(sameSessionNewSource,managed);
        byte[] brokenOriginal=raw.clone();brokenOriginal[brokenOriginal.length-1]^=1;Files.write(laterRoot.resolve(laterKey+".cop1"),brokenOriginal);
        RecordingLibrary.Session nowDamaged=RecordingLibrary.sessions(laterRoot).get(0);
        if(nowDamaged.state!=RecordingLibrary.SessionState.DAMAGED)throw new AssertionError("damage fixture was not detected");
        ManagedAudioParts.ClearResult damagedClear=ManagedAudioParts.clear(nowDamaged,managed);
        if(damagedClear.removedAttempts!=2||damagedClear.retainedAttempts!=0)throw new AssertionError("damaged source prevented clearing decoded cache");
        if(!Arrays.equals(Files.readAllBytes(laterRoot.resolve(laterKey+".cop1")),brokenOriginal))throw new AssertionError("damaged source changed while clearing cache");
        ManagedAudioParts.prepare(session,managed);
        ManagedAudioParts.ClearResult keyClear=ManagedAudioParts.clearBySessionKey(MeetingStore.sessionKey(descriptor),managed);
        if(keyClear.removedAttempts!=1||keyClear.retainedAttempts!=0)throw new AssertionError("stable key did not clear v2 cache");
        if(!Files.exists(unknown.resolve("unexpected-file")))throw new AssertionError("v1 unidentifiable cache should remain");
        try{NativeAudio.decodeParts(session,partDir);throw new AssertionError("existing parts overwritten");}catch(java.io.IOException expected){}
        if(!Arrays.equals(Files.readAllBytes(split.parts.get(0).path),output))throw new AssertionError("existing part changed");
        if(args.length==4) {
            Path publicDir=Paths.get(args[1]),model=Paths.get(args[2]),asrCache=Paths.get(args[3]);
            Path publicParts=Files.createDirectory(root.resolve("public-parts"));
            String[] names={"first.wav","silence.wav","last.wav"};long[] lengths={320000,32000,320000};
            java.util.List<NativeAudio.Part> ordered=new java.util.ArrayList<>();long start=0;
            for(int i=0;i<names.length;i++) {
                Path destination=publicParts.resolve(String.format(java.util.Locale.ROOT,"part-%08d.wav",i));
                Files.copy(publicDir.resolve(names[i]),destination);
                ordered.add(new NativeAudio.Part(destination,start,lengths[i]));start+=lengths[i];
            }
            DecodedAudioParts.save(new NativeAudio.PartsResult(publicParts,start,true,ordered,java.util.Collections.emptyList(),DeviceBookmarkCache.fingerprint(session)));
            byte[] publicBefore=java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(ordered.get(2).path));
            RecordingAudioRange.Result<String> publicGap=RecordingAudioRange.withRange(session,publicParts,root.resolve("public-range-temp"),22000,37000,
                selected->NativeLocalTranscription.transcribeDetailed(selected,model,model,asrCache));
            if(publicGap.retainedTemporary!=null||!publicGap.value.contains("\"durationMs\":15000")||publicGap.value.length()<100)
                throw new AssertionError("public gap did not reach the real local model");
            if(!Arrays.equals(publicBefore,java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(ordered.get(2).path))))
                throw new AssertionError("public source changed");
            String transcript=NativeLocalTranscription.transcribeDetailedParts(session,publicParts,model,model,asrCache);
            if(!transcript.contains("\"durationMs\":42000") || !transcript.contains("\"approximateTiming\":true") || transcript.length()<150)
                throw new AssertionError("real multipart JNI recognition missing timeline or text");
            Path progressCache=Files.createDirectory(root.resolve("progress-asr-cache"));
            java.util.List<Long> cancelledProgress=new java.util.ArrayList<>();
            try {
                NativeLocalTranscription.transcribeDetailedPartsWithProgress(session,publicParts,model,model,progressCache,(done,total)->{
                    if(total!=42000)throw new AssertionError("incorrect total audio duration");
                    cancelledProgress.add(done);return done==0;
                });
                throw new AssertionError("cancellation did not stop local transcription");
            } catch(java.util.concurrent.CancellationException expected) {}
            if(cancelledProgress.size()<2||cancelledProgress.get(0)!=0||cancelledProgress.get(1)<=0)
                throw new AssertionError("cancellation progress missing");
            java.util.Map<Path,byte[]> savedCache=new java.util.HashMap<>();
            try(java.util.stream.Stream<Path> entries=Files.list(progressCache)) {
                for(Path file:(Iterable<Path>)entries.filter(p->p.toString().endsWith(".json"))::iterator)
                    savedCache.put(file,Files.readAllBytes(file));
            }
            if(savedCache.isEmpty())throw new AssertionError("first completed window was not cached");
            java.util.List<Long> resumedProgress=new java.util.ArrayList<>();
            String resumed=NativeLocalTranscription.transcribeDetailedPartsWithProgress(session,publicParts,model,model,progressCache,(done,total)->{
                if(total!=42000||(!resumedProgress.isEmpty()&&done<resumedProgress.get(resumedProgress.size()-1)))
                    throw new AssertionError("progress is not monotonic");
                resumedProgress.add(done);return true;
            });
            if(!transcript.equals(resumed)||resumedProgress.get(0)!=0||resumedProgress.get(resumedProgress.size()-1)!=42000)
                throw new AssertionError("resumed result or progress differs");
            for(java.util.Map.Entry<Path,byte[]> entry:savedCache.entrySet())
                if(!Arrays.equals(entry.getValue(),Files.readAllBytes(entry.getKey())))throw new AssertionError("completed cache changed");
            java.util.List<Long> singleProgress=new java.util.ArrayList<>();
            String single=NativeLocalTranscription.transcribeDetailedWithProgress(ordered.get(0).path,model,model,progressCache,(done,total)->{
                if(total!=20000)throw new AssertionError("single WAV total mismatch");singleProgress.add(done);return true;
            });
            if(!single.contains("\"durationMs\":20000")||singleProgress.get(0)!=0||singleProgress.get(singleProgress.size()-1)!=20000)
                throw new AssertionError("single WAV progress mismatch");
            try {
                NativeLocalTranscription.transcribeDetailedWithProgress(ordered.get(0).path,model,model,progressCache,(done,total)->{throw new IllegalStateException("callback exception");});
                throw new AssertionError("callback exception did not propagate");
            } catch(IllegalStateException expected) {if(!"callback exception".equals(expected.getMessage()))throw expected;}
            for(int i=0;i<names.length;i++)
                if(!Arrays.equals(Files.readAllBytes(publicDir.resolve(names[i])),Files.readAllBytes(ordered.get(i).path)))
                    throw new AssertionError("public source or decoded parts changed");
            // The frontend will parse the detailed JSON; use a small explicit
            // text fixture here to test persistence and seek positions.
            MeetingStore meeting=new MeetingStore(root.resolve("meeting-parts"));String key="public-parts",text="第一段\n第二段";
            meeting.saveTranscription(key,null,text);
            java.util.List<MeetingStore.TranscriptWindow> timing=java.util.Arrays.asList(
                new MeetingStore.TranscriptWindow("第一段",0,20000),new MeetingStore.TranscriptWindow("第二段",22000,42000));
            meeting.saveTranscriptTiming(key,text,ordered.get(0).path,42000,timing);
            if(meeting.loadTranscriptTimingParts(key,session,publicParts)!=null)throw new AssertionError("single-file timing was mistaken for the part set");
            meeting.saveTranscriptTimingParts(key,text,session,publicParts,42000,timing);
            MeetingStore.TranscriptTiming saved=new MeetingStore(root.resolve("meeting-parts")).loadTranscriptTimingParts(key,session,publicParts);
            if(saved==null||saved.durationMs!=42000||saved.windows.size()!=2||saved.windows.get(1).startMs!=22000)
                throw new AssertionError("multipart transcript timing was not restored");
            if(meeting.loadTranscriptTiming(key,ordered.get(0).path)!=null)throw new AssertionError("single file was mistaken for all parts");
            try {if(meeting.loadTranscriptTimingParts(key,incomplete,publicParts)!=null)throw new AssertionError("different recording accepted");}
            catch(java.io.IOException expected){}
            try{meeting.saveTranscriptTimingParts(key,text,session,publicParts,20000,timing);throw new AssertionError("partial duration accepted");}catch(java.io.IOException expected){}
            try{NativeLocalTranscription.transcribeDetailedParts(incomplete,publicParts,model,model,asrCache);throw new AssertionError("accepted another recording's parts");}catch(java.io.IOException expected){}
            try{NativeTranscription.transcribeParts(session,publicParts,"","","",null);throw new AssertionError("empty cloud credentials accepted");}
            catch(java.io.IOException expected){if(!expected.getMessage().contains("configuration"))throw expected;}
            try{NativeTranscription.transcribeParts(incomplete,publicParts,"test","test","test",null);throw new AssertionError("cloud accepted another recording's parts");}
            catch(java.io.IOException expected){if(!expected.getMessage().contains("parts"))throw expected;}
            byte[] changedPart=Files.readAllBytes(ordered.get(2).path);changedPart[changedPart.length-1]^=1;Files.write(ordered.get(2).path,changedPart);
            try{NativeLocalTranscription.transcribeDetailedParts(session,publicParts,model,model,asrCache);throw new AssertionError("accepted a changed part");}catch(java.io.IOException expected){}
            try{meeting.loadTranscriptTimingParts(key,session,publicParts);throw new AssertionError("accepted altered part timing");}catch(java.io.IOException expected){}
            changedPart[changedPart.length-1]^=1;Files.write(ordered.get(2).path,changedPart);
            if(meeting.loadTranscriptTimingParts(key,session,publicParts)==null)throw new AssertionError("unchanged original timing unavailable");
            meeting.saveTranscription(key,text,"已修改文字");
            if(meeting.loadTranscriptTimingParts(key,session,publicParts)!=null)throw new AssertionError("edited text retained old positions");
            System.out.println("PASS Java-to-native public multipart transcription and receipt checks");
        }
        Path index=root.resolve("marks");DeviceBookmarkCache cache=new DeviceBookmarkCache(index);
        if(cache.load(session)!=null)throw new AssertionError("new recording already has an index");
        cache.save(session,result);DeviceBookmarkCache.Saved reopened=new DeviceBookmarkCache(index).load(session);
        if(reopened==null||reopened.samples!=640||!reopened.captureComplete||reopened.bookmarks.size()!=1||
           reopened.bookmarks.get(0).sequence!=1||reopened.bookmarks.get(0).playbackSamples!=320||reopened.bookmarks.get(0).elapsedMillis!=40)
            throw new AssertionError("device mark index did not reopen");
        if(cache.load(incomplete)!=null)throw new AssertionError("index leaked to a different session");
        try{cache.save(incomplete,result);throw new AssertionError("cross-session index was saved");}catch(java.io.IOException expected){}
        Path metadata=root.resolve(SegmentReceiver.key(descriptor)+".meta");byte[] synced=d.clone();synced[95]=1;crc.reset();crc.update(synced,0,108);put32(synced,108,crc.getValue());Files.write(metadata,synced);
        RecordingLibrary.Session received=RecordingLibrary.sessions(root).stream().filter(x->x.state==RecordingLibrary.SessionState.COMPLETE).findFirst().get();
        if(cache.load(received)==null)throw new AssertionError("receipt state invalidated identical recording");
        byte[] altered=synced.clone();altered[94]=1;crc.reset();crc.update(altered,0,108);put32(altered,108,crc.getValue());Files.write(metadata,altered);
        RecordingLibrary.Session changed=RecordingLibrary.sessions(root).stream().filter(x->x.state==RecordingLibrary.SessionState.COMPLETE).findFirst().get();
        if(cache.load(changed)!=null)throw new AssertionError("index accepted changed source metadata");
        Files.write(metadata,synced);
        Path indexFile;try(java.util.stream.Stream<Path> files=Files.list(index)){indexFile=files.filter(p->p.toString().endsWith(".device-marks")).findFirst().get();}
        byte[] damaged=Files.readAllBytes(indexFile);damaged[damaged.length-1]^=1;Files.write(indexFile,damaged);
        if(cache.load(received)!=null)throw new AssertionError("damaged index was accepted");
        cache.save(received,result);
        if(cache.load(received)==null||!Arrays.equals(Files.readAllBytes(root.resolve(SegmentReceiver.key(descriptor)+".cop1")),raw))
            throw new AssertionError("index retry changed original recording");
        try{NativeAudio.decode(session,wav);throw new AssertionError("existing output replaced");}catch(java.io.IOException expected){}
        if(!Arrays.equals(Files.readAllBytes(wav),output))throw new AssertionError("existing output changed");
        System.out.println("PASS Java-to-native synthetic audio decode and existing-output preservation");
    }
}
