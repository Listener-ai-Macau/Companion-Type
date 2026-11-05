package com.denzic.companion.mobile;

import java.io.*;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import java.util.zip.*;

/** Portable local backup of the recording, meeting and optional control directories.
 * Run on a worker while the host has stopped writers to these directories. */
public final class LibraryBackup {
    private LibraryBackup() {}
    private static final String MANIFEST = "companion-manifest-v1";
    private static final int MAGIC = 0x43424b31;
    private static final class Record {
        final String name; final Path path; final long size; final byte[] hash;
        Record(String n,Path p,long s,byte[] h){name=n;path=p;size=s;hash=h;}
    }
    private static MessageDigest sha(){try{return MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new AssertionError(e);}}
    private static String safe(String name)throws IOException {
        if(name==null||name.isEmpty()||name.startsWith("/")||name.indexOf('\\')>=0||name.indexOf('\0')>=0)throw new IOException("Invalid backup path");
        String[] parts=name.split("/",-1);
        if(parts.length<2||!(parts[0].equals("recordings")||parts[0].equals("meetings")||parts[0].equals("control")))throw new IOException("Unexpected backup folder");
        for(String part:parts)if(part.isEmpty()||part.equals(".")||part.equals("..")||part.indexOf(':')>=0)throw new IOException("Invalid backup path");
        return name;
    }
    private static List<Record> inventory(Path recordings,Path meetings,Path control)throws IOException {
        List<Record> result=new ArrayList<>();
        Path[] roots={recordings,meetings,control};String[] names={"recordings","meetings","control"};
        if(recordings==null||meetings==null)throw new IllegalArgumentException("recordings and meetings directories required");
        for(int i=0;i<roots.length;i++){
            final Path root=roots[i];final String prefix=names[i];
            if(root==null)continue;
            if(!Files.exists(root,LinkOption.NOFOLLOW_LINKS))throw new IOException("Backup source directory is missing");
            if(Files.isSymbolicLink(root)||!Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS))throw new IOException("Backup source is not a directory");
            try(java.util.stream.Stream<Path> paths=Files.walk(root)){
                Iterator<Path> it=paths.iterator();while(it.hasNext()){
                    Path path=it.next();if(path.equals(root))continue;
                    if(Files.isSymbolicLink(path))throw new IOException("Backup source contains a symbolic link");
                    if(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS))continue;
                    if(!Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS))throw new IOException("Backup source contains a non-file");
                    String relative=root.relativize(path).toString().replace(File.separatorChar,'/');
                    result.add(new Record(safe(prefix+"/"+relative),path,Files.size(path),null));
                }
            }
        }
        result.sort(Comparator.comparing(r->r.name));return result;
    }
    private static Record copyAndHash(String name,Path path,OutputStream out)throws IOException {
        BasicFileAttributes before=Files.readAttributes(path,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
        if(!before.isRegularFile())throw new IOException("Source file changed during backup");
        MessageDigest hash=sha();long size=0;byte[] b=new byte[65536];
        try(InputStream in=Files.newInputStream(path)){int n;while((n=in.read(b))!=-1){hash.update(b,0,n);out.write(b,0,n);size+=n;}}
        BasicFileAttributes after=Files.readAttributes(path,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
        if(!after.isRegularFile()||size!=before.size()||size!=after.size()||!before.lastModifiedTime().equals(after.lastModifiedTime())||!Objects.equals(before.fileKey(),after.fileKey()))throw new IOException("Source changed during backup; stop recording and retry");
        return new Record(name,path,size,hash.digest());
    }
    private static final OutputStream DISCARD=new OutputStream(){public void write(int n){} public void write(byte[] bytes,int off,int len){}};
    /** Writes a checksummed archive. The caller owns the stream and must discard it on failure. */
    public static void write(OutputStream output,Path recordings,Path meetings,Path control)throws IOException {
        if(output==null)throw new IllegalArgumentException("output required");
        List<Record> before=inventory(recordings,meetings,control),snapshot=new ArrayList<>(),written=new ArrayList<>();
        for(Record source:before){Record item=copyAndHash(source.name,source.path,DISCARD);if(item.size!=source.size)throw new IOException("Library changed during backup; retry");snapshot.add(item);}
        try(ZipOutputStream zip=new ZipOutputStream(new FilterOutputStream(output){@Override public void write(byte[] b,int off,int len)throws IOException {out.write(b,off,len);} @Override public void close() throws IOException {flush();}})){
        zip.setLevel(1);
        for(Record source:snapshot){zip.putNextEntry(new ZipEntry(source.name));Record item=copyAndHash(source.name,source.path,zip);if(item.size!=source.size||!Arrays.equals(item.hash,source.hash))throw new IOException("Library changed during backup; retry");written.add(item);zip.closeEntry();}
        List<Record> after=inventory(recordings,meetings,control);
        if(before.size()!=after.size())throw new IOException("Library changed during backup; retry");
        for(int i=0;i<written.size();i++){
            Record a=written.get(i),b=after.get(i);
            if(!a.name.equals(b.name)||a.size!=b.size)throw new IOException("Library changed during backup; retry");
            Record verify=copyAndHash(b.name,b.path,DISCARD);
            if(!Arrays.equals(a.hash,verify.hash))throw new IOException("Library changed during backup; retry");
        }
        zip.putNextEntry(new ZipEntry(MANIFEST));DataOutputStream manifest=new DataOutputStream(zip);
        manifest.writeInt(MAGIC);manifest.writeInt(written.size());
        for(Record record:written){manifest.writeUTF(record.name);manifest.writeLong(record.size);manifest.write(record.hash);}
        manifest.flush();zip.closeEntry();zip.finish();zip.flush();
        }
    }
    /** Restores to a NEW directory containing recordings/, meetings/ and control/.
     * Never merges into or overwrites an existing library. Caller owns the input. */
    public static void restore(InputStream input,Path newDirectory)throws IOException {
        restore(input,newDirectory,Long.MAX_VALUE,100000);
    }
    /** Host supplies its current disk budget; streaming extraction never publishes partial data. */
    public static void restore(InputStream input,Path newDirectory,long maxBytes,int maxFiles)throws IOException {
        if(input==null||newDirectory==null)throw new IllegalArgumentException("input and destination required");
        if(maxBytes<0||maxFiles<1)throw new IllegalArgumentException("invalid restore budget");
        Path target=newDirectory.toAbsolutePath().normalize(),parent=target.getParent();
        if(parent==null||!Files.isDirectory(parent)||Files.exists(target,LinkOption.NOFOLLOW_LINKS))throw new IOException("Choose a new destination directory");
        Path stage=Files.createTempDirectory(parent,".companion-restore-");boolean moved=false;
        try {
            for(String folder:new String[]{"recordings","meetings","control"})Files.createDirectory(stage.resolve(folder));
            Map<String,Record> files=new HashMap<>();try(ZipInputStream zip=new ZipInputStream(new FilterInputStream(input){@Override public void close(){}})){ZipEntry entry;boolean found=false;
            byte[] buffer=new byte[65536];long totalBytes=0;
            while((entry=zip.getNextEntry())!=null){
                String name=entry.getName();
                if(MANIFEST.equals(name)){
                    if(found||entry.isDirectory())throw new IOException("Invalid backup manifest");found=true;
                    DataInputStream manifest=new DataInputStream(zip);
                    if(manifest.readInt()!=MAGIC)throw new IOException("Unsupported backup format");int count=manifest.readInt();
                    if(count<0||count!=files.size())throw new IOException("Backup is incomplete");Set<String> checked=new HashSet<>();
                    for(int i=0;i<count;i++){
                        String path=safe(manifest.readUTF());long size=manifest.readLong();byte[] digest=new byte[32];manifest.readFully(digest);
                        Record record=files.get(path);if(record==null||!checked.add(path)||size!=record.size||!Arrays.equals(digest,record.hash))throw new IOException("Backup content does not match manifest");
                    }
                    if(zip.read()!=-1)throw new IOException("Invalid backup manifest");zip.closeEntry();
                    if(zip.getNextEntry()!=null)throw new IOException("Unexpected data after manifest");break;
                }
                if(found||entry.isDirectory())throw new IOException("Invalid backup entry");safe(name);
                if(files.containsKey(name))throw new IOException("Duplicate backup entry");
                if(files.size()>=maxFiles)throw new IOException("Backup contains too many files");
                Path dest=stage.resolve(name).normalize();if(!dest.startsWith(stage))throw new IOException("Invalid backup path");
                Files.createDirectories(dest.getParent());MessageDigest digest=sha();long size=0;
                try(OutputStream out=Files.newOutputStream(dest,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)){
                    int n;while((n=zip.read(buffer))!=-1){if(n>maxBytes-totalBytes)throw new IOException("Not enough space to restore backup");out.write(buffer,0,n);digest.update(buffer,0,n);size+=n;totalBytes+=n;}
                }
                files.put(name,new Record(name,dest,size,digest.digest()));zip.closeEntry();
            }
            if(!found)throw new IOException("Backup manifest missing");
            }
            Files.move(stage,target);moved=true;
        } finally {if(!moved)deleteStage(stage);}
    }
    private static void deleteStage(Path stage)throws IOException {
        if(!Files.exists(stage,LinkOption.NOFOLLOW_LINKS))return;
        try(java.util.stream.Stream<Path> paths=Files.walk(stage)){
            List<Path> all=new ArrayList<>();paths.forEach(all::add);all.sort(Comparator.reverseOrder());
            for(Path path:all)Files.deleteIfExists(path);
        }
    }
}
