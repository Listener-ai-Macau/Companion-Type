package com.denzic.companion.app;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Locale;
import java.util.zip.Deflater;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Streams already verified WAV parts to a user-selected destination. */
final class AudioExport {
    private AudioExport() {}
    static void write(List<Path> parts, OutputStream destination, boolean archive) throws IOException {
        if (parts == null || parts.isEmpty() || destination == null || (!archive && parts.size() != 1))
            throw new IOException("没有可导出的音频，请重新尝试。");
        if (!archive) {
            try (InputStream input = Files.newInputStream(parts.get(0))) { copy(input, destination); }
            return;
        }
        try (ZipOutputStream zip = new ZipOutputStream(destination)) {
            zip.setLevel(Deflater.NO_COMPRESSION);
            for (int i = 0; i < parts.size(); i++) {
                zip.putNextEntry(new ZipEntry(String.format(Locale.ROOT, "recording-%03d.wav", i + 1)));
                try (InputStream input = Files.newInputStream(parts.get(i))) { copy(input, zip); }
                zip.closeEntry();
            }
        }
    }
    private static void copy(InputStream input, OutputStream output) throws IOException {
        byte[] buffer = new byte[65536];
        int count;
        while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
    }
}
