import Foundation
import Security
import CompanionRecorderCore

struct TranscriptionConfig { let endpoint,model,key: String }
enum ProviderKey {
    private static let query: [String:Any] = [kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:"com.denzic.companion.mac.asr",kSecAttrAccount as String:"provider"]
    static func load() -> String {
        var q = query; q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne; var result: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary,&result) == errSecSuccess, let data = result as? Data else { return "" }; return String(decoding: data,as: UTF8.self)
    }
    static func save(_ value: String) throws {
        let data = Data(value.utf8)
        let status: OSStatus
        if value.isEmpty { let result = SecItemDelete(query as CFDictionary); status = result == errSecItemNotFound ? errSecSuccess : result }
        else {
            let result = SecItemUpdate(query as CFDictionary,[kSecValueData as String:data] as CFDictionary)
            if result == errSecItemNotFound { var q = query; q[kSecValueData as String] = data; status = SecItemAdd(q as CFDictionary,nil) } else { status = result }
        }
        guard status == errSecSuccess else { throw RecorderError.invalid("无法保存服务密钥到系统钥匙串。") }
    }
}
final class TranscriptionService: NSObject, URLSessionTaskDelegate {
    func urlSession(_ session: URLSession,task: URLSessionTask,willPerformHTTPRedirection response: HTTPURLResponse,newRequest request: URLRequest,completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
    func transcribe(_ wav: URL,config: TranscriptionConfig) async throws -> String {
        guard let endpoint = URL(string: config.endpoint), ["https","http"].contains(endpoint.scheme),
              endpoint.host != nil, !config.model.isEmpty else { throw RecorderError.invalid("请先在设置中填写转写服务地址和模型。原音已保存。") }
        let boundary = "Companion-"+UUID().uuidString
        let temporary = wav.deletingLastPathComponent().appendingPathComponent("asr-\(UUID().uuidString).multipart")
        FileManager.default.createFile(atPath: temporary.path,contents: nil); defer { try? FileManager.default.removeItem(at: temporary) }
        let output = try FileHandle(forWritingTo: temporary), input = try FileHandle(forReadingFrom: wav)
        defer { try? output.close(); try? input.close() }
        try output.write(contentsOf: Data("--\(boundary)\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n\(config.model)\r\n--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"recording.wav\"\r\nContent-Type: audio/wav\r\n\r\n".utf8))
        while let data = try input.read(upToCount: 65536), !data.isEmpty { try Task.checkCancellation(); try output.write(contentsOf: data) }
        try output.write(contentsOf: Data("\r\n--\(boundary)--\r\n".utf8)); try output.synchronize()
        var request = URLRequest(url: endpoint); request.httpMethod = "POST"; request.timeoutInterval = 120
        request.setValue("multipart/form-data; boundary=\(boundary)",forHTTPHeaderField: "Content-Type")
        if !config.key.isEmpty { request.setValue("Bearer "+config.key,forHTTPHeaderField: "Authorization") }
        let session = URLSession(configuration: .ephemeral,delegate: self,delegateQueue: nil); defer { session.invalidateAndCancel() }
        let (data,response) = try await session.upload(for: request,fromFile: temporary)
        guard let response = response as? HTTPURLResponse, (200..<300).contains(response.statusCode),
              let object = try JSONSerialization.jsonObject(with: data) as? [String:Any],
              let text = object["text"] as? String, !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw RecorderError.invalid("转写服务没有返回有效文字；原音已保存，可以重试。")
        }
        return text
    }
}
