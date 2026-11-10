import SwiftUI
import CompanionRecorderCore

struct ContentView: View {
    @Bindable var store: AppStore
    var body: some View {
        NavigationSplitView {
            List(selection: $store.selectedNote) {
                ForEach(store.notes) { note in
                    VStack(alignment: .leading,spacing: 3) {
                        Text(note.createdAt,format: .dateTime.month().day().hour().minute())
                        Text(note.transcript?.prefix(50).description ?? (note.cancelled ? "已取消输入 · 原音保留" : "原音已保存")).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                    }.tag(note.id)
                }
            }.listStyle(.sidebar).navigationTitle("录音")
        } detail: {
            VStack(alignment: .leading,spacing: 18) {
                HStack {
                    Picker("录音卡",selection: $store.selectedDevice) { Text("选择录音卡").tag(nil as UUID?); ForEach(store.devices) { Text($0.name).tag(Optional($0.id)) } }.frame(maxWidth: 300)
                    Button("扫描",action: store.scan).disabled(store.busy)
                    Button("连接",action: store.connect).disabled(store.busy || store.selectedDevice == nil)
                    Button("继续收取",action: store.resumeReceive).disabled(!store.connected || store.busy)
                }
                HStack {
                    Button(store.desktop ? "切换为录音模式" : "启用电脑按住说话") { store.setDesktop(!store.desktop) }.disabled(!store.connected || store.busy)
                    Text(store.desktop ? "按住说话 · 松开输入" : "单击开始 · 再单击停止").foregroundStyle(.secondary)
                }
                Text(store.status).foregroundStyle(.secondary).textSelection(.enabled).accessibilityLabel("设备状态："+store.status)
                if store.spaceConfirmationPending {
                    Text("原音已保存在本机。设备空间确认未完成，可点“继续收取”重试。").font(.caption).foregroundStyle(.orange)
                }
                Divider()
                if let note = store.currentNote {
                    ScrollView { VStack(alignment: .leading,spacing: 16) {
                        Text(note.transcript ?? "这段录音还没有转写。原音和重点已保存在本机。").textSelection(.enabled).frame(maxWidth: .infinity,alignment: .leading)
                        if !note.marks.isEmpty { Text("重点位置").font(.headline); ForEach(note.marks, id: \.sequence) { Text("\($0.sequence) · \(Double($0.sampleOffset)/16000,specifier: "%.2f") 秒") } }
                    }.padding(.vertical,8) }
                    HStack { Button("显示原音",action: store.reveal); Button("导出原件",action: store.export); Button("转写这段",action: store.retryTranscription).disabled(store.busy); Button("复制文字",action: store.copyText).disabled(note.transcript == nil) }
                } else { ContentUnavailableView("原音与笔记保存在本机",systemImage: "waveform",description: Text("连接录音卡后启用电脑模式。把光标放在编辑器里，按住卡片按键说话。")) }
                Spacer(minLength: 0)
            }.padding(24).frame(minWidth: 660,minHeight: 460)
        }.navigationSplitViewStyle(.balanced)
    }
}
