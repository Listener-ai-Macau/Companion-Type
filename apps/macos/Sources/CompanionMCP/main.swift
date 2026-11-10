import Foundation
import CompanionRecorderCore

// Local stdio only. This process has no keys, cloud client, erase or recorder controls.
let args = CommandLine.arguments
let custom = args.firstIndex(of: "--library").flatMap { $0+1 < args.count ? URL(fileURLWithPath: args[$0+1]) : nil }
let library = LocalLibrary(root: custom)
func content(_ value: Any) throws -> [[String:Any]] {
    let data = try JSONSerialization.data(withJSONObject: value,options: [.sortedKeys,.fragmentsAllowed])
    return [["type":"text","text":String(decoding: data,as: UTF8.self)]]
}
func object<T: Encodable>(_ value: T) throws -> Any { try JSONSerialization.jsonObject(with: JSONEncoder().encode(value)) }
func handle(_ request: [String:Any]) throws -> [String:Any] {
    let method = request["method"] as? String ?? ""
    let params = request["params"] as? [String:Any] ?? [:]
    switch method {
    case "initialize":
        let proposed = params["protocolVersion"] as? String ?? ""
        let version = ["2025-11-25","2025-06-18","2024-11-05"].contains(proposed) ? proposed : "2025-11-25"
        return ["protocolVersion":version,"serverInfo":["name":"companion-local-notes","version":"0.1.0"],
                "capabilities":["tools":[:],"resources":[:]],"instructions":"Local originals and device-authored highlight timestamps remain authoritative; unknown transcript is not a completed transcription."]
    case "ping": return [:]
    case "tools/list":
        return ["tools":[
            ["name":"search_notes","description":"Search locally saved Companion transcripts and recording IDs.","inputSchema":["type":"object","properties":["query":["type":"string"]],"required":["query"],"additionalProperties":false],"annotations":["readOnlyHint":true,"destructiveHint":false,"openWorldHint":false]],
            ["name":"read_note","description":"Read one local note, exact original identities and device highlight timestamps.","inputSchema":["type":"object","properties":["id":["type":"string"]],"required":["id"],"additionalProperties":false],"annotations":["readOnlyHint":true,"destructiveHint":false,"openWorldHint":false]]]]
    case "tools/call":
        let name = params["name"] as? String ?? "", arguments = params["arguments"] as? [String:Any] ?? [:]
        if name == "search_notes", let query = arguments["query"] as? String {
            let notes = try library.list().filter { query.isEmpty || $0.id.localizedCaseInsensitiveContains(query) || ($0.transcript ?? "").localizedCaseInsensitiveContains(query) }
            return ["content":try content(try object(notes))]
        }
        if name == "read_note", let id = arguments["id"] as? String { return ["content":try content(try object(library.load(id))) ] }
        throw RecorderError.invalid("Unknown tool or arguments")
    case "resources/list":
        return ["resources":try library.list().map { ["uri":"companion://notes/\($0.id)","name":$0.id,"mimeType":"application/json"] }]
    case "resources/read":
        guard let raw = params["uri"] as? String, let uri = URL(string: raw), uri.scheme == "companion", uri.host == "notes" else { throw RecorderError.invalid("Unknown local resource") }
        let note = try library.load(String(uri.path.dropFirst()))
        let text = String(decoding: try JSONEncoder().encode(note),as: UTF8.self)
        return ["contents":[["uri":raw,"mimeType":"application/json","text":text]]]
    default: throw RecorderError.invalid("Unsupported MCP method")
    }
}
while let line = readLine() {
    var response: [String:Any]
    do {
        guard let request = try JSONSerialization.jsonObject(with: Data(line.utf8)) as? [String:Any] else { throw RecorderError.invalid("Invalid JSON-RPC object") }
        guard let id = request["id"] else { continue }
        do { response = ["jsonrpc":"2.0","id":id,"result":try handle(request)] }
        catch { response = ["jsonrpc":"2.0","id":id,"error":["code":-32602,"message":error.localizedDescription]] }
    } catch { response = ["jsonrpc":"2.0","id":NSNull(),"error":["code":-32700,"message":"Invalid JSON-RPC request"]] }
    let data = try JSONSerialization.data(withJSONObject: response,options: [.sortedKeys])
    FileHandle.standardOutput.write(data); FileHandle.standardOutput.write(Data([10]))
}
