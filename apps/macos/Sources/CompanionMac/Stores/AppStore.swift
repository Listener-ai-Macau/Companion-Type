import AppKit
import Observation
import CompanionRecorderCore

@MainActor @Observable final class AppStore {
    var devices: [RecorderDevice] = []
    var selectedDevice: UUID?
    var connected = false
    var desktop = false
    var status = "连接录音卡后，可以选择按住说话。"
    var busy = false
    var notes: [RecorderNote] = []
    var selectedNote: String?
    var endpoint = UserDefaults.standard.string(forKey: "asr.endpoint") ?? ""
    var model = UserDefaults.standard.string(forKey: "asr.model") ?? ""
    var apiKey = ProviderKey.load()
    var flick = false
    var shake = false
    var undo = true
    @ObservationIgnored let bluetooth = RecorderBluetooth()
    @ObservationIgnored let insertion = TextInsertion()
    @ObservationIgnored private let library: LocalLibrary
    @ObservationIgnored private var lastSequence: UInt32 = 0
    private struct Dictation { var session: UInt64?; let target: TextInsertion.Target?; var cancelled = false, submit = false; let config: TranscriptionConfig }
    @ObservationIgnored private var dictations: [UInt32:Dictation] = [:]
    @ObservationIgnored private var pending: [(UInt64,Dictation)] = []
    @ObservationIgnored private var processing = false
    @ObservationIgnored private var queued: Set<UInt64> = []
    init() {
        library = LocalLibrary()
        bluetooth.devicesChanged = { [weak self] in self?.devices = $0 }
        bluetooth.disconnected = { [weak self] in self?.connected = false; self?.desktop = false; self?.status = $0 }
        bluetooth.statusChanged = { [weak self] in self?.receive($0) }
        reload()
    }
    func reload() { do { notes = try library.list() } catch { status = error.localizedDescription } }
    func scan() { do { try bluetooth.scan(); status = "请选择这块录音卡，再连接。" } catch { status = error.localizedDescription } }
    func connect() {
        guard let selectedDevice else { return }; busy = true
        Task { defer { busy = false }; do { try await bluetooth.connect(selectedDevice); connected = true; let current = try await bluetooth.mode(nil); lastSequence = current.sequence; status = "已连接。录音模式单击开停；电脑模式按住说话。" } catch { status = error.localizedDescription } }
    }
    func setDesktop(_ enabled: Bool) {
        busy = true
        Task { defer { busy = false }; do {
            let options: UInt8 = (flick ? 1 : 0) | (shake ? 2 : 0) | (undo ? 4 : 0)
            let reply = try await bluetooth.mode(enabled ? 1 : 0,options: enabled ? options : 0)
            lastSequence = reply.sequence; desktop = reply.mode == 1
            status = desktop ? "按住卡片按键说话，松开后输入文字。" : "录音模式：按一下开始，再按一下停止。"
        } catch { status = error.localizedDescription } }
    }
    func saveProvider() { do { try ProviderKey.save(apiKey); UserDefaults.standard.set(endpoint,forKey: "asr.endpoint"); UserDefaults.standard.set(model,forKey: "asr.model"); status = "转写配置已保存在本机，密钥存入系统钥匙串。" } catch { status = error.localizedDescription } }
    private func receive(_ value: InputStatus) {
        desktop = value.mode == 1
        let phases = ["状态未知","已就绪","准备录音","正在采音","已暂停","正在保存","原音已保存","存储空间不足","录音异常","正在升级","正在暂停","正在继续"]
        if Int(value.feedback) < phases.count { status = phases[Int(value.feedback)] }
        if value.flags & 16 != 0 { status += " · 重点已保存" } else if value.flags & 8 != 0 { status += " · 正在保存重点" }
        if value.sequence != lastSequence {
            lastSequence = value.sequence
            if value.events & 1 != 0, value.mode == 1 {
                dictations[value.token] = Dictation(target: insertion.capture(),config: TranscriptionConfig(endpoint: endpoint,model: model,key: apiKey))
            }
            if value.events & 16 != 0 { dictations[value.token]?.cancelled = true }
            if value.events & 32 != 0 { dictations[value.token]?.submit = true }
            if value.events & 8 != 0 { do { try insertion.undo(); status = "已撤销上一次语音输入。" } catch { status = error.localizedDescription } }
            if value.events & 64 != 0 { insertion.slide(previous: false) }
            if value.events & 128 != 0 { insertion.slide(previous: true) }
        }
        if value.flags & 2 != 0, value.session != 0 { dictations[value.token]?.session = value.session }
        if value.feedback == 6, let context = dictations[value.token], let session = context.session, value.session == session, !queued.contains(session) {
            queued.insert(session); pending.append((session,context)); processNext()
        }
    }
    private func processNext() {
        guard !processing, !pending.isEmpty, let peer = bluetooth.peer else { return }
        processing = true; let (session,context) = pending.removeFirst()
        Task {
            defer { processing = false; processNext() }
            do {
                status = "正在收取原音…"
                let descriptors = try await bluetooth.receive(session: session,library: library)
                let folder = try library.folder(RecorderNote.identity(peer: peer,session: session))
                let marks = try await AudioDecoder.decode(descriptors,folder: folder)
                var note = RecorderNote(peer: peer,session: session,originals: descriptors,marks: marks); note.cancelled = context.cancelled
                try library.save(note); reload(); selectedNote = note.id
                do { try await bluetooth.confirmSaved(note,library: library); note.reclaimed = true; try library.save(note) }
                catch { status = "原音已保存，设备空间确认稍后可重试。" }
                if context.cancelled { status = "这次输入已取消，原音保留在本机。"; return }
                status = "正在转写…"
                let text = try await TranscriptionService().transcribe(folder.appendingPathComponent("audio.wav"),config: context.config)
                note.transcript = text; try library.save(note); reload()
                try await insertion.insert(text,target: context.target,submit: context.submit); status = "文字已发送到输入位置。"
            } catch { status = error.localizedDescription; queued.remove(session); reload() }
        }
    }
    var currentNote: RecorderNote? { notes.first { $0.id == selectedNote } }
    func reveal() { do { guard let note = currentNote else { return }; NSWorkspace.shared.activateFileViewerSelecting([try library.folder(note.id).appendingPathComponent("audio.wav")]) } catch { status = error.localizedDescription } }
    func export() {
        guard let note = currentNote else { return }; let panel = NSOpenPanel(); panel.canChooseFiles = false; panel.canChooseDirectories = true; panel.canCreateDirectories = true; panel.prompt = "导出原件"
        if panel.runModal() == .OK, let destination = panel.url { do { let exported = try library.export(note,into: destination); status = "已导出原音、重点和文字。"; NSWorkspace.shared.activateFileViewerSelecting([exported]) } catch { status = error.localizedDescription } }
    }
    func copyText() { guard let text = currentNote?.transcript else { return }; NSPasteboard.general.clearContents(); NSPasteboard.general.setString(text,forType: .string) }
}
