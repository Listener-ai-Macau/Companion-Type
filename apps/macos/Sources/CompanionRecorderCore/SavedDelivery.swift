/// The original must already be durable locally. User delivery and the device
/// receipt can then overlap; the next device transfer still waits for cleanup.
@MainActor public enum SavedDelivery {
    public static func run(reclaim: @escaping @MainActor () async -> Void,
                           deliver: @MainActor () async throws -> Void) async throws {
        let maintenance = Task { await reclaim() }
        do {
            try await deliver()
        } catch {
            await maintenance.value
            throw error
        }
        await maintenance.value
    }
}
