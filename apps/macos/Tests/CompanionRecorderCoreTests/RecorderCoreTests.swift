import XCTest
@testable import CompanionRecorderCore

final class RecorderCoreTests: XCTestCase {
    func bytes(_ hex: String) -> Data { Data(stride(from: 0,to: hex.count,by: 2).map { i in UInt8(hex.dropFirst(i).prefix(2),radix: 16)! }) }
    func peer(uid: Data = Data(1...12),epoch: UInt64 = 0x1122334455667788) throws -> RecorderPeer {
        var p = Data(repeating: 0,count: 116); p[0] = 1; p.put(UInt32(0x57424155),at: 12); p.replaceSubrange(20..<32,with: uid)
        p.replaceSubrange(84..<88,with: Data("CRV2".utf8)); p.put(UInt16(2),at: 88); p.put(UInt16(32),at: 90)
        p.put(UInt32(7),at: 92); p.put(epoch,at: 96); p.put(UInt16(509),at: 108); p.put(Data(p[84..<112]).crc32,at: 112)
        return try RecorderPeer(status: p)
    }
    func fixture(_ name: String) throws -> [String:Any] {
        let p = Bundle.module.url(forResource: name,withExtension: "json",subdirectory: "Fixtures")!
        return try JSONSerialization.jsonObject(with: Data(contentsOf: p)) as! [String:Any]
    }
    func testExistingDirectoryGoldenAndIdentity() throws {
        let f = try fixture("recording-wire"), p = try peer()
        let descriptors = try (f["descriptorsHex"] as! [String]).map { try SegmentDescriptor(bytes($0),peer: p) }
        XCTAssertEqual(descriptors.map(\.index),[0,1,2]); XCTAssertEqual(descriptors.last?.totalSegments,3)
        let pages = try (f["pagesHex"] as! [String]).map { try DirectoryPage(bytes($0),peer: p) }
        for wire in (f["pagesHex"] as! [String]).map(bytes) {
            XCTAssertTrue(DirectoryPage.matches(wire,nonce: UInt32(wire.uint(16,4))))
            XCTAssertFalse(DirectoryPage.matches(wire,nonce: UInt32(wire.uint(16,4)) &+ 1))
        }
        var refusal = Data([67,82,69,50,2,0,16,0]); refusal.append(contentsOf: [9,0,0,0,3,0,0,0])
        XCTAssertTrue(DirectoryPage.matches(refusal,nonce: 9)); XCTAssertFalse(DirectoryPage.matches(refusal,nonce: 10))
        refusal[4] = 3; XCTAssertFalse(DirectoryPage.matches(refusal,nonce: 9))
        XCTAssertEqual(pages.flatMap(\.entries),descriptors)
        let payload = bytes(f["payloadHex"] as! String); try descriptors[0].verify(payload)
        var changed = payload; changed[14] ^= 1; XCTAssertThrowsError(try descriptors[0].verify(changed))
        XCTAssertThrowsError(try SegmentDescriptor(bytes((f["descriptorsHex"] as! [String])[0]),peer: peer(uid: Data(repeating: 9,count: 12))))
    }
    func testActualFirmwareCINProducer() throws {
        let f = try fixture("cin1-producer"), wire = bytes(f["wire"] as! String)
        let p = try peer(uid: wire.subdata(in: 40..<52),epoch: wire.uint(52,8)), status = try InputStatus(wire,peer: p)
        XCTAssertEqual(status.result,0); XCTAssertEqual(status.mode,1); XCTAssertEqual(status.options,7)
        let request = p.inputRequest(mode: 1,options: 7,nonce: 123)
        XCTAssertEqual(request.count,36); XCTAssertEqual(request.uint(8,4),123)
        XCTAssertEqual(Data(request.prefix(32)).crc32,UInt32(request.uint(32,4)))
        var bad = wire; bad[28] ^= 1; XCTAssertThrowsError(try InputStatus(bad,peer: p))
    }
    func testSavedShortCaptureWithoutIntermediateMicNotice() throws {
        let p = try peer()
        func input(_ feedback: UInt8,flags: UInt8 = 0,token: UInt32 = 17,session: UInt64 = 42,result: UInt8 = 0) throws -> InputStatus {
            var wire = Data(repeating: 0,count: 64)
            wire.replaceSubrange(0..<4,with: Data("CIN1".utf8)); wire[4] = 1; wire[5] = result; wire[6] = 1
            wire[7] = flags; wire[23] = feedback; wire.put(token,at: 24); wire.put(session,at: 28)
            wire.replaceSubrange(40..<52,with: p.uid); wire.put(p.epoch,at: 52); wire.put(Data(wire.prefix(60)).crc32,at: 60)
            return try InputStatus(wire,peer: p)
        }
        XCTAssertNil(try input(2,flags: 5).savedSession(forPhysicalToken: 17,observedSession: nil))
        XCTAssertEqual(try input(6).savedSession(forPhysicalToken: 17,observedSession: nil),42)
        XCTAssertEqual(try input(6).savedSession(forPhysicalToken: 17,observedSession: 42),42)
        XCTAssertNil(try input(6).savedSession(forPhysicalToken: 18,observedSession: nil))
        XCTAssertNil(try input(6).savedSession(forPhysicalToken: 17,observedSession: 41))
        XCTAssertNil(try input(6,session: 0).savedSession(forPhysicalToken: 17,observedSession: nil))
        XCTAssertNil(try input(6,flags: 2).savedSession(forPhysicalToken: 17,observedSession: nil))
        XCTAssertNil(try input(6,result: 1).savedSession(forPhysicalToken: 17,observedSession: nil))
        XCTAssertNil(try input(1).savedSession(forPhysicalToken: 17,observedSession: nil))
    }
    func testPacketCRCResumeAndTerminalSHA() throws {
        let f = try fixture("recording-wire"), p = try peer(), payload = bytes(f["payloadHex"] as! String)
        let d = try SegmentDescriptor(bytes((f["descriptorsHex"] as! [String])[0]),peer: p)
        func packet(offset: Int,count: Int,sequence: UInt32,final: Bool) -> Data {
            let head = final ? 56 : 24; var wire = Data(repeating: 0,count: head); wire[0] = 1; wire[1] = final ? 1 : 0
            wire.put(UInt16(count),at: 2); wire.put(d.recordingID,at: 4); wire.put(sequence,at: 8); wire.put(UInt32(offset),at: 12); wire.put(d.encodedLength,at: 16)
            let data = payload.subdata(in: offset..<(offset+count)); var crc = wire.subdata(in: 4..<20); crc.append(data); wire.put(crc.crc32,at: 20)
            if final { wire.replaceSubrange(24..<56,with: bytes(d.sha256)) }; wire.append(data); return wire
        }
        var receiver = SegmentPackets(d); let first = packet(offset: 0,count: 10,sequence: 0,final: false)
        XCTAssertTrue(try receiver.accept(first)); XCTAssertFalse(try receiver.accept(first)); XCTAssertFalse(receiver.complete)
        var resumed = SegmentPackets(d,prefix: receiver.bytes)
        XCTAssertTrue(try resumed.accept(packet(offset: 10,count: 5,sequence: 0,final: true))); XCTAssertTrue(resumed.complete); XCTAssertEqual(resumed.bytes,payload)
        var corrupt = packet(offset: 0,count: 15,sequence: 0,final: true); corrupt[20] ^= 1
        var rejected = SegmentPackets(d); XCTAssertThrowsError(try rejected.accept(corrupt)); XCTAssertFalse(rejected.complete)
        let receipt = d.receipt(peer: p); XCTAssertEqual(receipt.count,84); XCTAssertEqual(Data(receipt.prefix(80)).crc32,UInt32(receipt.uint(80,4)))
    }
    func testLocalLibraryAndOriginalExport() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString), export = root.appendingPathComponent("export")
        let lib = LocalLibrary(root: root.appendingPathComponent("library")), p = try peer(), f = try fixture("recording-wire")
        let d = try SegmentDescriptor(bytes((f["descriptorsHex"] as! [String])[0]),peer: p)
        var note = RecorderNote(peer: p,session: d.session,originals: [d],marks: []); note.transcript = "Public software fixture only"
        let folder = try lib.folder(note.id); try bytes(f["payloadHex"] as! String).write(to: folder.appendingPathComponent("original-0.cop1"))
        try Data("public software fixture".utf8).write(to: folder.appendingPathComponent("audio.wav")); try lib.save(note)
        XCTAssertEqual(try lib.list().map(\.id),[note.id]); XCTAssertEqual(try lib.load(note.id).transcript,note.transcript)
        try FileManager.default.createDirectory(at: export,withIntermediateDirectories: true)
        let target = try lib.export(note,into: export)
        XCTAssertEqual(try Data(contentsOf: target.appendingPathComponent("original-0.cop1")),bytes(f["payloadHex"] as! String))
        XCTAssertThrowsError(try lib.load("../note")); XCTAssertThrowsError(try lib.export(note,into: export))
    }
}
