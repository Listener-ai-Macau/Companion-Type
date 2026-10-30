package com.denzic.companion.mobile;

import java.io.IOException;

public final class NativeCalendarJvmTest {
    public static void main(String[] args) throws Exception {
        String input = "{\"sessionKey\":\"synthetic\",\"title\":\"Meeting\","
            + "\"tasks\":[{\"text\":\"Review sample\",\"completed\":false,"
            + "\"due\":\"2026-11-02T14:00:00+08:00\"}],\"reminderMinutes\":30}";
        String output = NativeCalendar.export(input);
        if (!output.contains("DTSTART:20261102T060000Z") || !output.contains("PT30M"))
            throw new AssertionError("calendar result missing expected time or reminder");
        try {
            NativeCalendar.export("{}");
            throw new AssertionError("invalid request was accepted");
        } catch (IOException expected) { }
        System.out.println("NativeCalendar JNI test passed");
    }
}
