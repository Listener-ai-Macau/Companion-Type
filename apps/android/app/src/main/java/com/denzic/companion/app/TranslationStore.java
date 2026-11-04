package com.denzic.companion.app;

import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;

/** Saved translation is independent of the AI connection and immutable recognition. */
final class TranslationStore {
    private static final int MAGIC=0x43545231, MAX_BYTES=4*1024*1024;
    private final Path directory;
    TranslationStore(Path directory){this.directory=directory;}
    static final class Entry {
        final String key,language,source,text;
        final long revision;
        Entry(String key,String language,String source,long revision,String text){
            this.key=key;this.language=language;this.source=source;this.revision=revision;this.text=text;
        }
        boolean matches(String currentSource){return source.equals(currentSource);}
    }
    private static MessageDigest digest(){
        try{return MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException error){throw new AssertionError(error);}
    }
    private Path file(String key){
        if(key==null||key.isEmpty())throw new IllegalArgumentException("recording key required");
        StringBuilder name=new StringBuilder();
        for(byte value:digest().digest(key.getBytes(StandardCharsets.UTF_8)))name.append(String.format(java.util.Locale.ROOT,"%02x",value&255));
        return directory.resolve(name+".translation");
    }
    private static void validate(Entry entry){
        if(entry==null||entry.key==null||entry.key.isEmpty()||entry.revision<=0||entry.source==null||entry.source.trim().isEmpty()
            ||entry.text==null||entry.text.trim().isEmpty()||!Arrays.asList("en","zh","ja","ko").contains(entry.language))
            throw new IllegalArgumentException("complete translation and source required");
    }
    private static void write(DataOutputStream output,String value)throws IOException{
        byte[] bytes=value.getBytes(StandardCharsets.UTF_8);
        if(bytes.length>MAX_BYTES)throw new IOException("translation is too large");
        output.writeInt(bytes.length);output.write(bytes);
    }
    private static String read(DataInputStream input)throws IOException{
        int size=input.readInt();
        if(size<0||size>MAX_BYTES||size>input.available())throw new IOException("saved translation is incomplete");
        byte[] bytes=new byte[size];input.readFully(bytes);
        return new String(bytes,StandardCharsets.UTF_8);
    }
    synchronized void save(Entry entry)throws IOException{
        validate(entry);
        ByteArrayOutputStream buffer=new ByteArrayOutputStream();DataOutputStream output=new DataOutputStream(buffer);
        output.writeInt(MAGIC);write(output,entry.key);write(output,entry.language);output.writeLong(entry.revision);
        write(output,entry.source);write(output,entry.text);output.flush();
        byte[] body=buffer.toByteArray();
        if(body.length>MAX_BYTES-32)throw new IOException("translation is too large");
        buffer.write(digest().digest(body));
        Files.createDirectories(directory);
        Path temporary=Files.createTempFile(directory,".translation-",".tmp");
        try{
            try(FileChannel channel=FileChannel.open(temporary,StandardOpenOption.WRITE)){
                java.nio.ByteBuffer bytes=java.nio.ByteBuffer.wrap(buffer.toByteArray());
                while(bytes.hasRemaining())channel.write(bytes);
                channel.force(true);
            }
            Files.move(temporary,file(entry.key),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
        }finally{Files.deleteIfExists(temporary);}
    }
    synchronized Entry load(String key)throws IOException{
        Path file=file(key);if(!Files.exists(file))return null;
        long size=Files.size(file);if(size<52||size>MAX_BYTES)throw new IOException("saved translation is damaged");
        byte[] bytes=Files.readAllBytes(file);
        if(bytes.length!=size)throw new IOException("saved translation changed while reading");
        byte[] body=Arrays.copyOf(bytes,bytes.length-32),checksum=Arrays.copyOfRange(bytes,bytes.length-32,bytes.length);
        if(!MessageDigest.isEqual(digest().digest(body),checksum))throw new IOException("saved translation checksum is invalid");
        DataInputStream input=new DataInputStream(new ByteArrayInputStream(body));
        if(input.readInt()!=MAGIC)throw new IOException("unsupported saved translation");
        String savedKey=read(input),language=read(input);long revision=input.readLong();
        Entry entry=new Entry(savedKey,language,read(input),revision,read(input));
        if(!key.equals(savedKey)||input.available()!=0)throw new IOException("saved translation does not match this recording");
        try{validate(entry);}catch(IllegalArgumentException error){throw new IOException("saved translation is invalid",error);}
        return entry;
    }
}
