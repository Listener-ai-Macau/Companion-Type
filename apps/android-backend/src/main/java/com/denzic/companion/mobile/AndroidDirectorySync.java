package com.denzic.companion.mobile;

import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import java.io.FileDescriptor;
import java.io.IOException;
import java.nio.file.Path;

/** Explicitly sync the directory entry before asking the card to reclaim audio. */
final class AndroidDirectorySync {
    private AndroidDirectorySync() {}
    private static final class DirectoryFd implements AutoCloseable {
        final FileDescriptor fd;
        DirectoryFd(FileDescriptor fd){this.fd=fd;}
        @Override public void close() throws ErrnoException {Os.close(fd);}
    }
    static void sync(Path directory) throws IOException {
        try (DirectoryFd handle=new DirectoryFd(Os.open(directory.toString(),
                OsConstants.O_RDONLY|OsConstants.O_CLOEXEC|OsConstants.O_NOFOLLOW,0))) {
            if(!OsConstants.S_ISDIR(Os.fstat(handle.fd).st_mode))
                throw new IOException("recording storage path is not a directory");
            Os.fsync(handle.fd);
        } catch(ErrnoException|SecurityException error) {
            throw new IOException("cannot safely save recording directory",error);
        }
    }
}
