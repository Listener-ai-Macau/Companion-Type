import SwiftUI

struct SettingsView: View {
    @Bindable var store: AppStore
    var body: some View {
        Form {
            Section("转写服务") {
                TextField("兼容转写 API 的完整地址",text: $store.endpoint)
                TextField("模型名称",text: $store.model)
                SecureField("自己的 API key；本地服务可留空",text: $store.apiKey)
                Button("保存配置",action: store.saveProvider)
                Text("原音始终保存在本机。启用电脑输入后，转写使用这里配置的服务；无需 Companion 订阅。").font(.caption).foregroundStyle(.secondary)
            }
            Section("可选手势 · 切换电脑模式后生效") {
                Toggle("双敲撤销上次语音输入",isOn: $store.undo)
                Toggle("摇动取消当前输入",isOn: $store.shake)
                Toggle("按住甩动结束并发送回车",isOn: $store.flick)
            }
            Section("输入权限") {
                Button("允许输入到其它应用") { store.insertion.requestPermission() }
                Text("用于把文字输入编辑器。输入位置变化时，结果保留在录音笔记中供复制。").font(.caption).foregroundStyle(.secondary)
            }
            Text(store.status).font(.caption).foregroundStyle(.secondary)
        }.formStyle(.grouped).frame(width: 570,height: 520)
    }
}
