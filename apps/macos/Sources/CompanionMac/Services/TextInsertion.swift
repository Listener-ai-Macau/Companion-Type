import AppKit
import ApplicationServices
import CompanionRecorderCore

@MainActor final class TextInsertion {
    struct Target { let process: pid_t; let element: AXUIElement }
    private struct LastInsertion { let target: Target; let range: CFRange; let text, replaced: String }
    private var last: LastInsertion?
    var permitted: Bool { AXIsProcessTrusted() }
    func requestPermission() { _ = AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String:true] as CFDictionary) }
    func capture() -> Target? {
        guard permitted, let app = NSWorkspace.shared.frontmostApplication, app.processIdentifier != ProcessInfo.processInfo.processIdentifier else { return nil }
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(AXUIElementCreateSystemWide(),kAXFocusedUIElementAttribute as CFString,&value) == .success,
              let value, CFGetTypeID(value) == AXUIElementGetTypeID() else { return nil }
        return Target(process: app.processIdentifier,element: unsafeBitCast(value,to: AXUIElement.self))
    }
    private func focused(_ target: Target) -> Bool {
        guard NSWorkspace.shared.frontmostApplication?.processIdentifier == target.process, let current = capture() else { return false }
        return CFEqual(current.element,target.element)
    }
    private func string(_ element: AXUIElement,_ attribute: String) -> String? {
        var result: CFTypeRef?; guard AXUIElementCopyAttributeValue(element,attribute as CFString,&result) == .success else { return nil }; return result as? String
    }
    private func selection(_ element: AXUIElement) -> CFRange? {
        var result: CFTypeRef?, range = CFRange()
        guard AXUIElementCopyAttributeValue(element,kAXSelectedTextRangeAttribute as CFString,&result) == .success,
              let result, CFGetTypeID(result) == AXValueGetTypeID(), AXValueGetValue(unsafeBitCast(result,to: AXValue.self),.cfRange,&range) else { return nil }; return range
    }
    private func key(_ code: CGKeyCode,flags: CGEventFlags = []) {
        for down in [true,false] { let event = CGEvent(keyboardEventSource: nil,virtualKey: code,keyDown: down); event?.flags = flags; event?.post(tap: .cghidEventTap) }
    }
    func insert(_ text: String,target: Target?,submit: Bool) async throws {
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { throw RecorderError.invalid("没有识别出文字，原音已保存。") }
        guard let target, focused(target) else { throw RecorderError.invalid("输入位置已经变化。文字已保存在这里，可以复制。") }
        let range = selection(target.element), replaced = string(target.element,kAXSelectedTextAttribute) ?? ""
        let direct = AXUIElementSetAttributeValue(target.element,kAXSelectedTextAttribute as CFString,text as CFString) == .success
        if !direct {
            // Retain the user's clipboard and restore only if nobody changed it after our paste.
            let board = NSPasteboard.general
            let old = board.pasteboardItems?.map { item -> NSPasteboardItem in
                let copy = NSPasteboardItem(); for type in item.types { if let data = item.data(forType: type) { copy.setData(data,forType: type) } }; return copy
            } ?? []
            board.clearContents(); board.setString(text,forType: .string); let version = board.changeCount
            key(9,flags: .maskCommand); try await Task.sleep(for: .milliseconds(250))
            if board.changeCount == version { board.clearContents(); if !old.isEmpty { board.writeObjects(old) } }
        }
        if let range { last = LastInsertion(target: target,range: CFRange(location: range.location,length: text.utf16.count),text: text,replaced: replaced) }
        else { last = nil }
        if submit {
            guard focused(target) else { throw RecorderError.invalid("文字已输入，窗口已变化，因此保留在草稿中。") }
            key(36)
        }
    }
    func undo() throws {
        guard let last, focused(last.target), let value = string(last.target.element,kAXValueAttribute) else { throw RecorderError.invalid("无法定位上次输入，请使用编辑器的撤销。") }
        let text = value as NSString
        guard last.range.location >= 0,last.range.location+last.range.length <= text.length,
              text.substring(with: NSRange(location: last.range.location,length: last.range.length)) == last.text else { throw RecorderError.invalid("上次输入已经改动，请使用编辑器的撤销。") }
        var range = last.range
        guard let selected = AXValueCreate(.cfRange,&range),
              AXUIElementSetAttributeValue(last.target.element,kAXSelectedTextRangeAttribute as CFString,selected) == .success,
              AXUIElementSetAttributeValue(last.target.element,kAXSelectedTextAttribute as CFString,last.replaced as CFString) == .success else { throw RecorderError.invalid("当前编辑器不支持精确撤销，请使用编辑器的撤销。") }
        self.last = nil
    }
    func slide(previous: Bool) { key(previous ? 123 : 124) }
}
