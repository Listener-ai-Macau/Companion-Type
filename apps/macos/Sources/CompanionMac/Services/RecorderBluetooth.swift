import Foundation
@preconcurrency import CoreBluetooth
import CompanionRecorderCore

struct RecorderDevice: Identifiable { let id: UUID; let name: String; let rssi: Int }

@MainActor final class RecorderBluetooth: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    var devicesChanged: (([RecorderDevice]) -> Void)?
    var statusChanged: ((InputStatus) -> Void)?
    var disconnected: ((String) -> Void)?
    private var central: CBCentralManager!
    private var discoveries: [UUID:(CBPeripheral,RecorderDevice)] = [:]
    private var peripheral: CBPeripheral?
    private var chars: [CBUUID:CBCharacteristic] = [:]
    private var inbox: [CBUUID:[Data]] = [:]
    private var waits: [CBUUID:Wait] = [:]
    private var subscriptions: [CBUUID:CheckedContinuation<Void,Error>] = [:]
    private var connection: CheckedContinuation<Void,Error>?
    private var discovery: CheckedContinuation<Void,Error>?
    private var servicesLeft = 0
    private(set) var peer: RecorderPeer?
    private class Wait {
        let id = UUID(); let match: (Data) -> Bool; let continuation: CheckedContinuation<Data,Error>
        var timeout: Task<Void,Never>?
        init(_ match: @escaping (Data) -> Bool,_ continuation: CheckedContinuation<Data,Error>) { self.match = match; self.continuation = continuation }
    }
    override init() { super.init(); central = CBCentralManager(delegate: self,queue: .main) }
    static func uuid(_ n: UInt16) -> CBUUID { CBUUID(string: String(format: "8f7a%04x-7b7d-4f3d-9d6f-6c2d1b7c0000",n)) }
    func scan() throws {
        guard central.state == .poweredOn else { throw RecorderError.invalid("请先开启并允许 Companion 使用蓝牙。") }
        discoveries.removeAll(); devicesChanged?([]); central.scanForPeripherals(withServices: nil)
        Task { try? await Task.sleep(for: .seconds(10)); central.stopScan() }
    }
    func centralManagerDidUpdateState(_ central: CBCentralManager) { if central.state != .poweredOn { fail(RecorderError.invalid("蓝牙当前不可用。")) } }
    func centralManager(_ central: CBCentralManager,didDiscover p: CBPeripheral,advertisementData: [String:Any],rssi RSSI: NSNumber) {
        let name = advertisementData[CBAdvertisementDataLocalNameKey] as? String ?? p.name ?? ""
        guard name.localizedCaseInsensitiveContains("companion") || name.localizedCaseInsensitiveContains("capture") else { return }
        discoveries[p.identifier] = (p,RecorderDevice(id: p.identifier,name: name,rssi: RSSI.intValue))
        devicesChanged?(discoveries.values.map(\.1).sorted { $0.rssi > $1.rssi })
    }
    func connect(_ id: UUID) async throws {
        guard let selected = discoveries[id]?.0 else { throw RecorderError.invalid("请先扫描并选择录音卡。") }
        central.stopScan(); peripheral = selected; chars.removeAll(); inbox.removeAll(); selected.delegate = self
        let setupTimeout = Task { [weak self] in
            try? await Task.sleep(for: .seconds(20)); guard !Task.isCancelled else { return }
            self?.fail(RecorderError.invalid("连接准备超时，请确认系统配对提示。")); self?.central.cancelPeripheralConnection(selected)
        }
        defer { setupTimeout.cancel() }
        try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void,Error>) in connection = c; central.connect(selected) }
        try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void,Error>) in discovery = c; selected.discoverServices(nil) }
        // A protected read requests pairing before choosing the current CRV2 protocol.
        let settings = try await read(0x4001)
        if settings.count >= 13, settings[0] == 1 {
            var clock = Data(settings.prefix(13)); clock.append(Data(repeating: 0,count: 4))
            var calendar = Calendar(identifier: .gregorian); calendar.timeZone = TimeZone(secondsFromGMT: 0)!
            let now = Date(), components = calendar.dateComponents([.hour,.minute,.second],from: Date())
            clock[10] = UInt8(components.hour ?? 0); clock[11] = UInt8(components.minute ?? 0); clock[12] = UInt8(components.second ?? 0)
            clock.put(UInt32(now.timeIntervalSince1970),at: 13); try write(0x4001,clock)
        }
        var status = try await read(0x1001)
        for _ in 0..<10 where status.count != 116 { try await Task.sleep(for: .milliseconds(200)); status = try await read(0x1001) }
        peer = try RecorderPeer(status: status)
        for n: UInt16 in [0x4001,0x3001,0x3002,0x3003,0x6001] { try await subscribe(n) }
        _ = try await mode(nil)
    }
    func disconnect() { if let peripheral { central.cancelPeripheralConnection(peripheral) } }
    func centralManager(_ central: CBCentralManager,didConnect peripheral: CBPeripheral) { connection?.resume(); connection = nil }
    func centralManager(_ central: CBCentralManager,didFailToConnect peripheral: CBPeripheral,error: Error?) { fail(error ?? RecorderError.invalid("连接失败，请重试。")) }
    func centralManager(_ central: CBCentralManager,didDisconnectPeripheral peripheral: CBPeripheral,error: Error?) {
        fail(error ?? RecorderError.invalid("录音卡已断开，录音仍由录音卡保存。")); peer = nil; disconnected?(error?.localizedDescription ?? "录音卡已断开")
    }
    func peripheral(_ peripheral: CBPeripheral,didDiscoverServices error: Error?) {
        if let error { fail(error); return }; let services = peripheral.services ?? []; servicesLeft = services.count
        if services.isEmpty { fail(RecorderError.invalid("未找到录音卡服务。")); return }
        for service in services { peripheral.discoverCharacteristics(nil,for: service) }
    }
    func peripheral(_ peripheral: CBPeripheral,didDiscoverCharacteristicsFor service: CBService,error: Error?) {
        if let error { fail(error); return }; for c in service.characteristics ?? [] { chars[c.uuid] = c }
        servicesLeft -= 1
        if servicesLeft == 0 {
            guard [0x1001,0x4001,0x3001,0x3002,0x3003,0x6001].allSatisfy({ chars[Self.uuid(UInt16($0))] != nil }) else { fail(RecorderError.invalid("当前固件缺少录音服务。")); return }
            discovery?.resume(); discovery = nil
        }
    }
    private func fail(_ error: Error) {
        connection?.resume(throwing: error); connection = nil; discovery?.resume(throwing: error); discovery = nil
        let old = waits; waits.removeAll(); for wait in old.values { wait.timeout?.cancel(); wait.continuation.resume(throwing: error) }
        let oldSubscriptions = subscriptions; subscriptions.removeAll(); for c in oldSubscriptions.values { c.resume(throwing: error) }
    }
    private func value(_ n: UInt16,matching match: @escaping (Data) -> Bool = { _ in true },start: (() -> Void)? = nil) async throws -> Data {
        let uuid = Self.uuid(n)
        return try await withCheckedThrowingContinuation { (c: CheckedContinuation<Data,Error>) in
            if waits[uuid] != nil { c.resume(throwing: RecorderError.invalid("另一项设备操作尚未结束。")); return }
            if start == nil, let index = inbox[uuid]?.firstIndex(where: match), let data = inbox[uuid]?.remove(at: index) { c.resume(returning: data); return }
            let wait = Wait(match,c); waits[uuid] = wait
            wait.timeout = Task { [weak self] in
                try? await Task.sleep(for: .seconds(15)); guard !Task.isCancelled, self?.waits[uuid]?.id == wait.id else { return }
                self?.waits[uuid] = nil; c.resume(throwing: RecorderError.invalid("设备回复超时；已保存的原音可以重试收取。"))
            }
            start?()
        }
    }
    private func write(_ n: UInt16,_ data: Data) throws {
        guard let peripheral, let c = chars[Self.uuid(n)], peripheral.state == .connected else { throw RecorderError.invalid("请先连接录音卡。") }
        peripheral.writeValue(data,for: c,type: .withResponse)
    }
    private func read(_ n: UInt16) async throws -> Data {
        guard let peripheral, let c = chars[Self.uuid(n)] else { throw RecorderError.invalid("设备服务未准备好。") }
        return try await value(n,start: { peripheral.readValue(for: c) })
    }
    private func exchange(_ request: Data,on n: UInt16,reply: UInt16,matching: @escaping (Data) -> Bool) async throws -> Data {
        guard let peripheral, let c = chars[Self.uuid(n)] else { throw RecorderError.invalid("设备服务未准备好。") }
        return try await value(reply,matching: matching,start: { peripheral.writeValue(request,for: c,type: .withResponse) })
    }
    private func subscribe(_ n: UInt16) async throws {
        guard let peripheral, let c = chars[Self.uuid(n)] else { throw RecorderError.invalid("设备服务未准备好。") }
        if c.isNotifying { return }
        try await withCheckedThrowingContinuation { (v: CheckedContinuation<Void,Error>) in subscriptions[c.uuid] = v; peripheral.setNotifyValue(true,for: c) }
    }
    func peripheral(_ peripheral: CBPeripheral,didUpdateNotificationStateFor characteristic: CBCharacteristic,error: Error?) {
        guard let c = subscriptions.removeValue(forKey: characteristic.uuid) else { return }; if let error { c.resume(throwing: error) } else { c.resume() }
    }
    func peripheral(_ peripheral: CBPeripheral,didWriteValueFor characteristic: CBCharacteristic,error: Error?) { if let error { fail(error) } }
    func peripheral(_ peripheral: CBPeripheral,didUpdateValueFor characteristic: CBCharacteristic,error: Error?) {
        if let error { fail(error); return }; guard let data = characteristic.value else { return }
        if characteristic.uuid == Self.uuid(0x4001), let peer, let status = try? InputStatus(data,peer: peer), status.request == 0 { statusChanged?(status); return }
        if let wait = waits[characteristic.uuid], wait.match(data) {
            waits[characteristic.uuid] = nil; wait.timeout?.cancel(); wait.continuation.resume(returning: data)
        } else {
            if inbox[characteristic.uuid,default: []].count >= 4096 { fail(RecorderError.invalid("接收队列已满，请重新连接并续传。")); return }
            inbox[characteristic.uuid,default: []].append(data)
        }
    }
    private func nonce() -> UInt32 { UInt32.random(in: 1...UInt32.max) }
    func mode(_ selected: UInt8?,options: UInt8 = 0) async throws -> InputStatus {
        guard let peer else { throw RecorderError.invalid("请先连接录音卡。") }; let nonce = nonce()
        let p = try await exchange(peer.inputRequest(mode: selected,options: options,nonce: nonce),on: 0x4001,reply: 0x4001) {
            $0.count == 64 && $0.prefix(4) == Data("CIN1".utf8) && $0.uint(8,4) == nonce
        }
        let result = try InputStatus(p,peer: peer)
        guard result.result == 0 else { throw RecorderError.invalid(result.result == 1 ? "请先松开按键并等待录音保存，再切换模式。" : "当前固件不支持这个模式。") }; return result
    }
    func catalog() async throws -> [SegmentDescriptor] {
        guard let peer, let peripheral else { throw RecorderError.invalid("请先连接录音卡。") }
        let capacity = UInt16(min(509,peripheral.maximumWriteValueLength(for: .withoutResponse)))
        let negotiate = try peer.negotiate(capacity: capacity,nonce: nonce())
        _ = try await exchange(negotiate,on: 0x3001,reply: 0x3001) { $0 == negotiate }
        let requestNonce = nonce(); var entries: [SegmentDescriptor] = [], generation: UInt32 = 0
        while true {
            var p = Data(repeating: 0,count: 16); p[0] = 2; p[1] = 0x20; p[2] = 1
            p.put(generation,at: 4); p.put(requestNonce,at: 8); p.put(UInt32(entries.count),at: 12)
            let raw = try await exchange(p,on: 0x3001,reply: 0x3002) { $0.count >= 20 && $0[0] == 2 && $0.uint(16,4) == requestNonce || $0.prefix(4) == Data("CRE2".utf8) }
            let page = try DirectoryPage(raw,peer: peer)
            guard page.start == entries.count, generation == 0 || generation == page.generation else { throw RecorderError.invalid("录音目录正在变化，请重新收取。") }
            generation = page.generation; entries.append(contentsOf: page.entries)
            if entries.count == page.total { return entries }
        }
    }
    func receive(session: UInt64,library: LocalLibrary) async throws -> [SegmentDescriptor] {
        guard let peer else { throw RecorderError.invalid("请先连接录音卡。") }
        let selected = try await catalog().filter { $0.session == session }.sorted { $0.index < $1.index }
        guard let last = selected.last, selected.first?.index == 0, last.flags & 2 == 2,
              last.totalSegments == selected.count else { throw RecorderError.invalid("录音尚未完整保存，请稍后收取。") }
        var next: UInt64 = 0
        for (i,d) in selected.enumerated() {
            guard d.index == i, d.sampleOffset == next else { throw RecorderError.invalid("录音中间分段缺失。") }; next += d.sampleCount
        }
        let folder = try library.folder(RecorderNote.identity(peer: peer,session: session))
        for d in selected {
            let original = folder.appendingPathComponent("original-\(d.index).cop1")
            if FileManager.default.fileExists(atPath: original.path) { try d.verify(Data(contentsOf: original)); continue }
            let partial = original.appendingPathExtension("partial"), binding = original.appendingPathExtension("checkpoint.json")
            var prefix = Data()
            if let data = try? Data(contentsOf: partial), let saved = try? JSONSerialization.jsonObject(with: Data(contentsOf: binding)) as? [String:Any],
               saved["descriptorSHA"] as? String == d.sha256, saved["prefixSHA"] as? String == data.sha256, data.count < d.encodedLength { prefix = data }
            var packets = SegmentPackets(d,prefix: prefix); inbox[Self.uuid(0x3003)] = []
            try write(0x3003,d.pull(peer: peer,offset: UInt32(prefix.count)))
            while !packets.complete {
                let p = try await value(0x3003) { $0.count >= 20 && $0[0] == 1 && $0.uint(4,4) == d.recordingID }
                _ = try packets.accept(p)
                if packets.bytes.count-prefix.count >= 65536 || packets.complete {
                    try packets.bytes.write(to: partial,options: .atomic)
                    let json: [String:Any] = ["descriptorSHA":d.sha256,"prefixSHA":packets.bytes.sha256]
                    try JSONSerialization.data(withJSONObject: json).write(to: binding,options: .atomic); prefix = packets.bytes
                }
            }
            try d.verify(packets.bytes); try packets.bytes.write(to: original,options: .atomic)
            let file = try FileHandle(forWritingTo: original); try file.synchronize(); try file.close()
        }
        return selected
    }
    func confirmSaved(_ note: RecorderNote,library: LocalLibrary) async throws {
        guard let peer, peer.uid.hex == note.deviceUID, peer.epoch == note.formatEpoch,
              try library.load(note.id).id == note.id else { throw RecorderError.invalid("本地副本或设备身份已变化。") }
        let folder = try library.folder(note.id)
        guard FileManager.default.fileExists(atPath: folder.appendingPathComponent("audio.wav").path) else { throw RecorderError.invalid("原音还没有完整保存。") }
        for descriptor in note.originals {
            try descriptor.verify(Data(contentsOf: folder.appendingPathComponent("original-\(descriptor.index).cop1")))
            let request = descriptor.receipt(peer: peer)
            _ = try await exchange(request,on: 0x6001,reply: 0x6001) { $0 == request }
        }
    }
}
