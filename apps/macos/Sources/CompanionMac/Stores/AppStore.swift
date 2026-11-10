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
    var spaceConfirmationPending = false
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
    private struct Dictation { var session: UInt64?; let peer: RecorderPeer; let target: TextInsertion.Target?; var cancelled = false, submit = false, finished = false; let config: TranscriptionConfig }
    @ObservationIgnored private var dictations: [String:Dictation] = [:]
    @ObservationIgnored private var pending: [(UInt64,Dictation)] = []
    @ObservationIgnored private var processing = false
    @ObservationIgnored private var queued: Set<String> = []
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
        Task { defer { busy = false }; do { try await bluetooth.connect(selectedDevice); connected = true; let current = try await bluetooth.mode(nil); lastSequence = current.sequence; receive(current); resumeReceive(); status = "已连接。录音模式单击开停；电脑模式按住说话。" } catch { status = error.localizedDescription } }
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
        guard let peer = bluetooth.peer else { return }
        let key = peer.uid.hex+"-"+String(peer.epoch)+"-"+String(value.token)
        desktop = value.mode == 1
        let phases = ["状态未知","已就绪","准备录音","正在采音","已暂停","正在保存","原音已保存","存储空间不足","录音异常","正在升级","正在暂停","正在继续"]
        // Idle/old-session device notices must not overwrite progress while a
        // saved recording is being received, transcribed or inserted.
        if !processing || value.flags & 2 != 0 {
            if Int(value.feedback) < phases.count { status = phases[Int(value.feedback)] }
            if value.flags & 16 != 0 { status += " · 重点已保存" } else if value.flags & 8 != 0 { status += " · 正在保存重点" }
        }
        if value.sequence != lastSequence {
            lastSequence = value.sequence
            if value.events & 1 != 0, value.mode == 1 {
                dictations[key] = Dictation(peer: peer,target: insertion.capture(),config: TranscriptionConfig(endpoint: endpoint,model: model,key: apiKey))
            }
            if value.events & 16 != 0 { dictations[key]?.cancelled = true }
            if value.events & 32 != 0 { dictations[key]?.submit = true }
            if value.events & 2 != 0 { dictations[key]?.finished = true }
            if value.events & 8 != 0 { do { try insertion.undo(); status = "已撤销上一次语音输入。" } catch { status = error.localizedDescription } }
            if value.events & 64 != 0 { insertion.slide(previous: false) }
            if value.events & 128 != 0 { insertion.slide(previous: true) }
        }
        if value.flags & 2 != 0, value.session != 0 { dictations[key]?.session = value.session }
        if value.feedback == 6, var context = dictations[key], let session = context.session, value.session == session {
            context.finished = true; dictations[key] = context
            enqueue(session,context: context)
        }
    }
    private func enqueue(_ session: UInt64,context: Dictation) {
        let id = RecorderNote.identity(peer: context.peer,session: session)
        guard !queued.contains(id) else { return }; queued.insert(id); pending.append((session,context)); processNext()
    }
    func resumeReceive() {
        guard let peer = bluetooth.peer else { return }
        for context in Array(dictations.values) where context.finished && context.peer.uid == peer.uid && context.peer.epoch == peer.epoch {
            if let session = context.session { enqueue(session,context: context) }
        }
        processNext()
    }
    private func processNext() {
        guard !processing, let peer = bluetooth.peer,
              let index = pending.firstIndex(where: { $0.1.peer.uid == peer.uid && $0.1.peer.epoch == peer.epoch }) else { return }
        processing = true; let (session,context) = pending.remove(at: index)
        Task {
            defer { processing = false; processNext() }
            do {
                status = "正在收取原音…"
                let folder = try library.folder(RecorderNote.identity(peer: peer,session: session))
                var note: RecorderNote
                if let saved = try? library.load(RecorderNote.identity(peer: peer,session: session)) { note = saved }
                else {
                    let descriptors = try await bluetooth.receive(session: session,library: library)
                    let marks = try await AudioDecoder.decode(descriptors,folder: folder)
                    note = RecorderNote(peer: peer,session: session,originals: descriptors,marks: marks); note.cancelled = context.cancelled
                }
                try library.save(note); reload(); selectedNote = note.id
                let saved = note
                try await SavedDelivery.run(reclaim: { [self] in
                    guard !saved.reclaimed else { return }
                    do {
                        try await bluetooth.confirmSaved(saved,library: library)
                        // Delivery may have saved a transcript while BLE was
                        // awaiting its receipt. Merge, never overwrite it.
                        var current = try library.load(saved.id)
                        current.reclaimed = true; try library.save(current)
                        spaceConfirmationPending = false; reload()
                    } catch { spaceConfirmationPending = true }
                }, deliver: { [self] in
                    if context.cancelled { status = "这次输入已取消，原音保留在本机。"; return }
                    if saved.transcript != nil { status = "原音与文字已经保存在本机，可以复制或导出。"; return }
                    status = "原音已保存，正在转写…"
                    do {
                        let text = try await TranscriptionService().transcribe(folder.appendingPathComponent("audio.wav"),config: context.config)
                        var current = try library.load(saved.id)
                        current.transcript = text; try library.save(current); reload()
                        try await insertion.insert(text,target: context.target,submit: context.submit)
                        status = "文字已发送到输入位置。"
                    } catch { status = error.localizedDescription; throw error }
                })
                if (try? library.load(saved.id).reclaimed) != true { queued.remove(saved.id) }
            } catch { status = error.localizedDescription; queued.remove(RecorderNote.identity(peer: peer,session: session)); reload() }
        }
    }
    func retryTranscription() {
        guard var note = currentNote else { return }; busy = true
        let config = TranscriptionConfig(endpoint: endpoint,model: model,key: apiKey)
        Task { defer { busy = false }; do {
            status = "正在转写已保存的原音…"
            let folder = try library.folder(note.id)
            let text = try await TranscriptionService().transcribe(folder.appendingPathComponent("audio.wav"),config: config)
            note.transcript = text; try library.save(note); reload(); status = "转写完成，可以复制文字。"
        } catch { status = error.localizedDescription } }
    }
    var currentNote: RecorderNote? { notes.first { $0.id == selectedNote } }
    func reveal() { do { guard let note = currentNote else { return }; NSWorkspace.shared.activateFileViewerSelecting([try library.folder(note.id).appendingPathComponent("audio.wav")]) } catch { status = error.localizedDescription } }
    func export() {
        guard let note = currentNote else { return }; let panel = NSOpenPanel(); panel.canChooseFiles = false; panel.canChooseDirectories = true; panel.canCreateDirectories = true; panel.prompt = "导出原件"
        if panel.runModal() == .OK, let destination = panel.url { do { let exported = try library.export(note,into: destination); status = "已导出原音、重点和文字。"; NSWorkspace.shared.activateFileViewerSelecting([exported]) } catch { status = error.localizedDescription } }
    }
    func copyText() { guard let text = currentNote?.transcript else { return }; NSPasteboard.general.clearContents(); NSPasteboard.general.setString(text,forType: .string) }
}
