from pathlib import Path
B=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-audio-import-backend20261110/apps/android-backend/src/main/java/com/denzic/companion/mobile')
def patch(name,pairs):
 p=B/name;t=p.read_text(encoding='utf8')
 for old,new in pairs:
  assert t.count(old)==1,(name,old[:90],t.count(old));t=t.replace(old,new)
 p.write_text(t,encoding='utf8')
patch('RecordingLibrary.java',[
 ('public final long startedUnixSeconds;','public final long startedUnixSeconds;\n        public final ImportedAudio imported;\n        public String key(){return imported!=null?imported.key:MeetingStore.sessionKey(segments.get(0).descriptor);}\n        private Session(ImportedAudio value){state=SessionState.COMPLETE;segments=Collections.emptyList();startedUnixSeconds=0;imported=value;}'),
 ('this.state=state;this.segments=','this.imported=null;this.state=state;this.segments='),
 ('if(key==null||!key.matches(', 'if(ImportedAudio.validKey(key)){List<Session> found=new ArrayList<>();List<MetadataProblem> issues=new ArrayList<>();Path p=directory.resolve(ImportedAudio.folder(key));if(Files.exists(p,LinkOption.NOFOLLOW_LINKS))try{found.add(new Session(ImportedAudio.read(p)));}catch(IOException e){issues.add(new MetadataProblem(p,e.getMessage()));}return new Inventory(Collections.unmodifiableList(found),issues);}\n        if(key==null||!key.matches('),
 ('return new Inventory(Collections.unmodifiableList(sessions),problems);','if(selectedPrefix==null&&Files.exists(directory))try(DirectoryStream<Path> imports=Files.newDirectoryStream(directory,"import-*")){for(Path folder:imports){if(!folder.getFileName().toString().matches("import-[0-9a-f]{64}"))continue;try{sessions.add(new Session(ImportedAudio.read(folder)));}catch(IOException error){problems.add(new MetadataProblem(folder,error.getMessage()));}}}\n        return new Inventory(Collections.unmodifiableList(sessions),problems);')])
patch('ManagedAudioParts.java',[
 ('byte[] fingerprint=DeviceBookmarkCache.fingerprint(session);','if(session.imported!=null)return session.imported.verifiedParts();\n        byte[] fingerprint=DeviceBookmarkCache.fingerprint(session);')])
patch('NativeAudio.java',[
 ('if(session.state==RecordingLibrary.SessionState.DAMAGED)throw new IOException("recording is damaged; originals retained");\n        int count=', 'if(session.imported!=null)return new VerifiedPrefix(session.imported.samples,true,Collections.emptyList());\n        if(session.state==RecordingLibrary.SessionState.DAMAGED)throw new IOException("recording is damaged; originals retained");\n        int count='),
 ('return DecodedAudioParts.load(directory.toAbsolutePath(),DeviceBookmarkCache.fingerprint(session));','if(session.imported!=null){if(!session.imported.directory.equals(directory.toAbsolutePath().normalize()))throw new IOException("导入音频来源不符。");return session.imported.verifiedParts();}\n        return DecodedAudioParts.load(directory.toAbsolutePath(),DeviceBookmarkCache.fingerprint(session));')])
patch('DeviceBookmarkCache.java',[
 ('String key=MeetingStore.sessionKey(session.segments.get(0).descriptor);','String key=session.key();'),
 ('if(session==null||session.segments.isEmpty())throw new IllegalArgumentException("recording session required");','if(session!=null&&session.imported!=null)return session.imported.fingerprint();\n        if(session==null||session.segments.isEmpty())throw new IllegalArgumentException("recording session required");')])
print('Imported source is typed independently of recorder protocol; unchanged device branches retained.')
