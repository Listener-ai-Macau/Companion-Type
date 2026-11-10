import SwiftUI
import AppKit

@main struct CompanionMacApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @State private var store = AppStore()
    var body: some Scene {
        WindowGroup("Companion",id: "main") { ContentView(store: store) }
        Settings { SettingsView(store: store) }
        MenuBarExtra("Companion",systemImage: "waveform") {
            Text(store.connected ? "录音卡已连接" : "录音卡未连接")
            Button(store.desktop ? "录音模式" : "按住说话") { store.setDesktop(!store.desktop) }.disabled(!store.connected)
            SettingsLink { Text("设置…") }
            Divider(); Button("退出 Companion") { NSApp.terminate(nil) }
        }
    }
}
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) { NSApp.setActivationPolicy(.regular); NSApp.activate(ignoringOtherApps: true) }
}
