import Foundation
import CryptoKit

public enum RecorderError: Error, LocalizedError {
    case invalid(String)
    public var errorDescription: String? { if case let .invalid(s) = self { return s }; return nil }
}
public extension Data {
    func uint(_ at: Int, _ bytes: Int) -> UInt64 {
        (0..<bytes).reduce(UInt64(0)) { $0 | UInt64(self[at + $1]) << (8 * $1) }
    }
    mutating func put<T: FixedWidthInteger>(_ value: T, at: Int) {
        var v = value.littleEndian
        Swift.withUnsafeBytes(of: &v) { replaceSubrange(at..<(at + $0.count), with: $0) }
    }
    var hex: String { map { String(format: "%02x", $0) }.joined() }
    var crc32: UInt32 {
        var crc: UInt32 = 0xffffffff
        for byte in self { crc ^= UInt32(byte); for _ in 0..<8 { crc = (crc >> 1) ^ (crc & 1 == 1 ? 0xedb88320 : 0) } }
        return ~crc
    }
    var sha256: String { SHA256.hash(data: self).map { String(format: "%02x", $0) }.joined() }
}
public struct RecorderPeer: Equatable, Codable {
    public let uid: Data
    public let epoch: UInt64
    public let maxValue: UInt16
    public init(status p: Data) throws {
        guard p.count == 116, p[0] == 1, p.uint(12,4) == 0x57424155,
              p.subdata(in: 84..<88) == Data("CRV2".utf8), p.uint(88,2) == 2,
              p.uint(90,2) == 32, p.uint(92,4) & 7 == 7,
              p.subdata(in: 84..<112).crc32 == p.uint(112,4), p.uint(96,8) != 0 else {
            throw RecorderError.invalid("录音卡身份或协议不完整，请重新连接。")
        }
        uid = p.subdata(in: 20..<32); epoch = p.uint(96,8); maxValue = UInt16(p.uint(108,2))
        guard uid != Data(repeating: 0,count: 12), uid != Data(repeating: 255,count: 12) else { throw RecorderError.invalid("设备身份无效。") }
    }
    public func inputRequest(mode: UInt8?, options: UInt8 = 0, nonce: UInt32) -> Data {
        var p = Data(repeating: 0,count: 36); p.replaceSubrange(0..<4,with: Data("CIN1".utf8)); p[4] = 1
        p[5] = mode == nil ? 0 : 1; p[6] = mode ?? 0; p[7] = options; p.put(nonce,at: 8)
        p.replaceSubrange(12..<24,with: uid); p.put(epoch,at: 24); p.put(Data(p.prefix(32)).crc32,at: 32); return p
    }
    public func negotiate(capacity: UInt16, nonce: UInt32) throws -> Data {
        guard capacity >= 136, nonce != 0 else { throw RecorderError.invalid("蓝牙包长尚未就绪。") }
        var p = Data(repeating: 0,count: 32); p[0] = 2; p[1] = 0x22; p.put(min(capacity,maxValue),at: 2); p.put(nonce,at: 4)
        p.replaceSubrange(8..<20,with: uid); p.put(epoch,at: 20); p.put(Data(p.prefix(28)).crc32,at: 28); return p
    }
}
public struct InputStatus: Equatable {
    public let result, mode, flags, options, feedback: UInt8
    public let request, sequence, eventTick, token, bookmark: UInt32
    public let events: UInt16
    public let session: UInt64
    public init(_ p: Data, peer: RecorderPeer) throws {
        guard p.count == 64, p.prefix(4) == Data("CIN1".utf8), p[4] == 1, p[6] <= 2,
              p.subdata(in: 40..<52) == peer.uid, p.uint(52,8) == peer.epoch,
              Data(p.prefix(60)).crc32 == p.uint(60,4) else { throw RecorderError.invalid("设备交互消息损坏或来源已变化。") }
        result = p[5]; mode = p[6]; flags = p[7]; options = p[22]; feedback = p[23]
        request = UInt32(p.uint(8,4)); sequence = UInt32(p.uint(12,4)); eventTick = UInt32(p.uint(16,4))
        events = UInt16(p.uint(20,2)); token = UInt32(p.uint(24,4)); session = p.uint(28,8); bookmark = UInt32(p.uint(36,4))
    }
}
public struct SegmentDescriptor: Equatable, Codable {
    public let recordingID, index, encodedLength, contentCRC, totalSegments: UInt32
    public let session, sampleOffset, sampleCount: UInt64
    public let flags: UInt8
    public let sha256: String
    public let startedUnix: UInt32
    public init(_ row: Data, peer: RecorderPeer) throws {
        guard [112,116].contains(row.count), row.prefix(4) == Data("CRS2".utf8), row.uint(4,2) == 2,
              row.uint(6,2) == 112, row.uint(12,8) == peer.epoch, row.subdata(in: 96..<108) == peer.uid,
              Data(row.prefix(108)).crc32 == row.uint(108,4), row[93] == 3,
              row[92] & 1 == 1, row.uint(8,4) != 0, row.uint(20,8) != 0,
              row.uint(48,4) >= 15, row.uint(48,4) <= 64*1024*1024, row.uint(40,8) > 0,
              row.uint(32,8) % 320 == 0, row.uint(40,8) % 320 == 0 else { throw RecorderError.invalid("录音分段身份或校验不匹配。") }
        recordingID = UInt32(row.uint(8,4)); session = row.uint(20,8); index = UInt32(row.uint(28,4))
        sampleOffset = row.uint(32,8); sampleCount = row.uint(40,8); encodedLength = UInt32(row.uint(48,4))
        contentCRC = UInt32(row.uint(52,4)); sha256 = row.subdata(in: 56..<88).hex
        totalSegments = UInt32(row.uint(88,4)); flags = row[92]; startedUnix = row.count == 116 ? UInt32(row.uint(112,4)) : 0
    }
    public func verify(_ raw: Data) throws {
        guard raw.count == encodedLength, raw.crc32 == contentCRC, raw.sha256 == sha256 else { throw RecorderError.invalid("原音长度、CRC 或 SHA 不一致，未确认回收。") }
    }
    public func pull(peer: RecorderPeer, offset: UInt32) -> Data {
        var p = Data(repeating: 0,count: 32); p[0] = 2; p[1] = 0x21; p.put(recordingID,at: 4)
        p.put(peer.epoch,at: 8); p.put(session,at: 16); p.put(index,at: 24); p.put(offset,at: 28); return p
    }
    public func receipt(peer: RecorderPeer) -> Data {
        var p = Data(repeating: 0,count: 84); p.replaceSubrange(0..<8,with: Data([67,82,65,50,2,0,84,0]))
        p.replaceSubrange(8..<20,with: peer.uid); p.put(peer.epoch,at: 20); p.put(session,at: 28)
        p.put(index,at: 36); p.put(recordingID,at: 40); p.put(encodedLength,at: 44)
        let hex = Array(sha256.utf8)
        for i in 0..<32 { p[48+i] = UInt8(String(decoding: hex[i*2..<(i*2+2)],as: UTF8.self),radix: 16)! }
        p.put(Data(p.prefix(80)).crc32,at: 80); return p
    }
}
public struct DirectoryPage {
    public let generation, start, total, nonce: UInt32
    public let entries: [SegmentDescriptor]
    public init(_ p: Data, peer: RecorderPeer) throws {
        guard p.count >= 24, p[0] == 2, p[1] <= 2, [112,116].contains(Int(p.uint(2,2))) else { throw RecorderError.invalid("目录页格式无效。") }
        let width = Int(p.uint(2,2)), count = Int(p[1]); var crc = p.subdata(in: 0..<20); crc.append(p.dropFirst(24))
        guard p.count == 24+width*count, crc.crc32 == p.uint(20,4) else { throw RecorderError.invalid("目录页校验失败。") }
        generation = UInt32(p.uint(4,4)); start = UInt32(p.uint(8,4)); total = UInt32(p.uint(12,4)); nonce = UInt32(p.uint(16,4))
        guard generation != 0, nonce != 0, total <= 64, start <= total, count <= Int(total-start), count > 0 || total == 0 else { throw RecorderError.invalid("目录快照无效。") }
        entries = try (0..<count).map { try SegmentDescriptor(p.subdata(in: (24+$0*width)..<(24+($0+1)*width)),peer: peer) }
    }
}
public struct SegmentPackets {
    public let descriptor: SegmentDescriptor
    public private(set) var bytes = Data()
    public private(set) var complete = false
    private var sequence: UInt32?
    public init(_ descriptor: SegmentDescriptor,prefix: Data = Data()) { self.descriptor = descriptor; bytes = prefix }
    public mutating func accept(_ p: Data) throws -> Bool {
        guard p.count >= 20, p[0] == 1, p.uint(4,4) == descriptor.recordingID else { return false }
        let final = p[1] & 1 == 1, compact = p[1] & 8 == 8
        let header = final ? 56 : compact ? 20 : 24, n = Int(p.uint(2,2)), offset = Int(p.uint(12,4))
        guard p[1] & 0xf6 == 0, p.count == header+n, p.count >= header,
              UInt64(offset)+UInt64(n) <= descriptor.encodedLength,
              compact || p.uint(16,4) == descriptor.encodedLength else { throw RecorderError.invalid("原音数据包边界不一致。") }
        let payload = p.subdata(in: header..<p.count); var fields = p.subdata(in: 4..<16)
        var total = Data(repeating: 0,count: 4); total.put(descriptor.encodedLength,at: 0); fields.append(total); fields.append(payload)
        guard fields.crc32 == p.uint(compact && !final ? 16 : 20,4) else { throw RecorderError.invalid("原音数据包 CRC 错误。") }
        if offset < bytes.count {
            guard offset+n <= bytes.count, bytes.subdata(in: offset..<(offset+n)) == payload else { throw RecorderError.invalid("续传前缀已变化。") }; return false
        }
        guard offset == bytes.count, sequence == nil || UInt32(p.uint(8,4)) == sequence! &+ 1 else { throw RecorderError.invalid("原音数据包缺失。") }
        sequence = UInt32(p.uint(8,4)); bytes.append(payload)
        if final {
            guard p.subdata(in: 24..<56).hex == descriptor.sha256 else { throw RecorderError.invalid("原音结束摘要不一致。") }
            try descriptor.verify(bytes); complete = true
        }
        return true
    }
}
