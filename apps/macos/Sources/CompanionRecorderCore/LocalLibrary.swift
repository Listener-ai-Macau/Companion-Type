import Foundation
import Darwin

public struct NoteMark: Codable, Equatable {
    public let sequence: UInt32
    public let sampleOffset, elapsedMs: UInt64
}
public struct RecorderNote: Codable, Identifiable, Equatable {
    public let id: String
    public let deviceUID: String
    public let formatEpoch, sessionID: UInt64
    public let createdAt: Date
    public var transcript: String?
    public var marks: [NoteMark]
    public var originals: [SegmentDescriptor]
    public var cancelled: Bool
    public var reclaimed: Bool
    public init(peer: RecorderPeer, session: UInt64, originals: [SegmentDescriptor], marks: [NoteMark]) {
        id = Self.identity(peer: peer,session: session); deviceUID = peer.uid.hex; formatEpoch = peer.epoch; sessionID = session
        let date = originals.first?.startedUnix ?? 0
        createdAt = date == 0 ? Date() : Date(timeIntervalSince1970: TimeInterval(date))
        transcript = nil; self.marks = marks; self.originals = originals; cancelled = false; reclaimed = false
    }
    public static func identity(peer: RecorderPeer, session: UInt64) -> String {
        peer.uid.hex + "-" + String(format: "%016llx",peer.epoch) + "-" + String(format: "%016llx",session)
    }
}
public struct LocalLibrary {
    public let root: URL
    public init(root: URL? = nil) {
        self.root = root ?? FileManager.default.urls(for: .applicationSupportDirectory,in: .userDomainMask)[0]
            .appendingPathComponent("Denzic/CompanionMac",isDirectory: true)
    }
    private func valid(_ id: String) -> Bool { id.range(of: "^[0-9a-f]{24}-[0-9a-f]{16}-[0-9a-f]{16}$",options: .regularExpression) != nil }
    public func folder(_ id: String) throws -> URL {
        guard valid(id) else { throw RecorderError.invalid("录音标识无效。") }
        let folder = root.appendingPathComponent(id,isDirectory: true)
        try FileManager.default.createDirectory(at: folder,withIntermediateDirectories: true); return folder
    }
    public func save(_ note: RecorderNote) throws {
        let directory = try folder(note.id), path = directory.appendingPathComponent("note.json")
        let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted,.sortedKeys]; encoder.dateEncodingStrategy = .iso8601
        try encoder.encode(note).write(to: path,options: .atomic)
        let file = try FileHandle(forWritingTo: path); try file.synchronize(); try file.close()
        let fd = open(directory.path,O_RDONLY); if fd >= 0 { defer { close(fd) }; guard fsync(fd) == 0 else { throw RecorderError.invalid("录音索引尚未保存到磁盘。") } }
    }
    public func load(_ id: String) throws -> RecorderNote {
        guard valid(id) else { throw RecorderError.invalid("录音标识无效。") }
        let p = root.appendingPathComponent(id).appendingPathComponent("note.json")
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        let note = try decoder.decode(RecorderNote.self,from: Data(contentsOf: p))
        guard note.id == id else { throw RecorderError.invalid("录音索引身份不一致。") }; return note
    }
    public func list() throws -> [RecorderNote] {
        guard FileManager.default.fileExists(atPath: root.path) else { return [] }
        return try FileManager.default.contentsOfDirectory(at: root,includingPropertiesForKeys: nil)
            .filter { valid($0.lastPathComponent) && FileManager.default.fileExists(atPath: $0.appendingPathComponent("note.json").path) }
            .map { try load($0.lastPathComponent) }.sorted { $0.createdAt > $1.createdAt }
    }
    public func export(_ note: RecorderNote, into destination: URL) throws -> URL {
        let source = try folder(note.id), target = destination.appendingPathComponent("Companion-"+note.id,isDirectory: true)
        guard !FileManager.default.fileExists(atPath: target.path) else { throw RecorderError.invalid("目标中已有这份导出，请选择其它位置。") }
        try FileManager.default.createDirectory(at: target,withIntermediateDirectories: false)
        for descriptor in note.originals {
            let file = source.appendingPathComponent("original-\(descriptor.index).cop1")
            try descriptor.verify(Data(contentsOf: file)); try FileManager.default.copyItem(at: file,to: target.appendingPathComponent(file.lastPathComponent))
        }
        for name in ["audio.wav","note.json"] { try FileManager.default.copyItem(at: source.appendingPathComponent(name),to: target.appendingPathComponent(name)) }
        if let text = note.transcript { try text.write(to: target.appendingPathComponent("transcript.txt"),atomically: true,encoding: .utf8) }
        return target
    }
}
