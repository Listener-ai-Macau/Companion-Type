import Foundation
import CompanionRecorderCore

enum AudioDecoder {
    static func decode(_ descriptors: [SegmentDescriptor],folder: URL) async throws -> [NoteMark] {
        let wav = folder.appendingPathComponent("audio.wav"), result = folder.appendingPathComponent("decode-result.json")
        if !FileManager.default.fileExists(atPath: wav.path) {
            let segments: [[String:Any]] = descriptors.map { d in
                ["path":folder.appendingPathComponent("original-\(d.index).cop1").path,"sampleOffset":d.sampleOffset,
                 "sampleCount":d.sampleCount,"encodedLength":d.encodedLength,"crc32":d.contentCRC,"sha256":d.sha256]
            }
            let job = folder.appendingPathComponent("decode-job.json")
            try JSONSerialization.data(withJSONObject: ["segments":segments,"output":wav.path]).write(to: job,options: .atomic)
            let helper = Bundle.main.bundleURL.appendingPathComponent("Contents/MacOS/companion-mac-audio")
            let data = try await Task.detached {
                let process = Process(), pipe = Pipe(); process.executableURL = helper; process.arguments = [job.path]; process.standardOutput = pipe
                try process.run(); let data = pipe.fileHandleForReading.readDataToEndOfFile(); process.waitUntilExit()
                guard process.terminationStatus == 0 else { throw RecorderError.invalid("原音解码没有完成，原文件已保留。") }; return data
            }.value
            try data.write(to: result,options: .atomic)
        }
        let object = try JSONSerialization.jsonObject(with: Data(contentsOf: result)) as? [String:Any]
        guard let timeline = object?["timeline"] as? [String:Any] else { throw RecorderError.invalid("原音边界信息不完整。") }
        return try JSONDecoder().decode([NoteMark].self,from: JSONSerialization.data(withJSONObject: timeline["bookmarks"] ?? []))
    }
}
