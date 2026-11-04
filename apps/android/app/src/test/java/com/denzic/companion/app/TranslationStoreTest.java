package com.denzic.companion.app;

import java.nio.file.*;
import java.util.Arrays;

/** Local persistence without Android, network credentials or a model runtime. */
public final class TranslationStoreTest {
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    public static void main(String[] args)throws Exception{
        Path root=Files.createTempDirectory(Paths.get(args[0]),"translation-store-");
        TranslationStore store=new TranslationStore(root);
        check(store.load("recording")==null,"missing translation should be empty");
        String original="原话、数字 24 与 emoji 🚀\n第二行";
        store.save(new TranslationStore.Entry("recording","ja",original,2,"保存された翻訳 🚀\n二行目"));
        TranslationStore.Entry saved=new TranslationStore(root).load("recording");
        check(saved!=null&&saved.revision==2&&saved.language.equals("ja")&&saved.text.contains("🚀"),"translation did not reopen");
        check(saved.matches(original)&&!saved.matches(original+"修订"),"changed source was not distinguished");
        check(store.load("other")==null,"translation crossed recording identity");
        Path file;
        try(java.util.stream.Stream<Path> files=Files.list(root)){
            file=files.filter(p->p.toString().endsWith(".translation")).findFirst().get();
        }
        byte[] before=Files.readAllBytes(file);
        try{store.save(new TranslationStore.Entry("recording","en",original,2,""));throw new AssertionError("empty result accepted");}
        catch(IllegalArgumentException expected){}
        check(Arrays.equals(before,Files.readAllBytes(file)),"failed save replaced the earlier result");
        store.save(new TranslationStore.Entry("other","en","other source",1,"Other translation"));
        check(new TranslationStore(root).load("recording").text.equals(saved.text),"other recording changed saved text");
        Files.write(file,new byte[]{1,2,3});
        try{store.load("recording");throw new AssertionError("damaged file accepted");}catch(java.io.IOException expected){}
        check(Files.size(file)==3,"unreadable translation evidence was removed");
        System.out.println("PASS translation reopening, Unicode, source changes, recording isolation and failed-save preservation");
    }
}
