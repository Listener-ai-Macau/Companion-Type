package android.system;
import java.io.FileDescriptor;
import java.util.ArrayList;
import java.util.List;
public final class Os {
    public static final List<String> calls=new ArrayList<>();
    public static String fail="";public static int flags,mode=040000;
    private static void call(String name)throws ErrnoException {calls.add(name);if(fail.equals(name))throw new ErrnoException(name,5);}
    public static FileDescriptor open(String path,int openFlags,int createMode)throws ErrnoException {flags=openFlags;call("open");return new FileDescriptor();}
    public static StructStat fstat(FileDescriptor fd)throws ErrnoException {call("fstat");return new StructStat(mode);}
    public static void fsync(FileDescriptor fd)throws ErrnoException {call("fsync");}
    public static void close(FileDescriptor fd)throws ErrnoException {call("close");}
}
