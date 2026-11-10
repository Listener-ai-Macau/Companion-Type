import XCTest
@testable import CompanionRecorderCore

final class SavedDeliveryTests: XCTestCase {
    @MainActor func testDeliveryStartsBeforeSlowReclaimAndNextTransferWaits() async throws {
        let reclaimStarted = expectation(description: "reclaim started")
        let delivered = expectation(description: "user delivery completed")
        var release: CheckedContinuation<Void,Never>?
        var reclaimFinished = false, workflowFinished = false
        let job = Task {
            try await SavedDelivery.run(reclaim: {
                await withCheckedContinuation { release = $0; reclaimStarted.fulfill() }
                reclaimFinished = true
            }, deliver: {
                XCTAssertFalse(reclaimFinished)
                delivered.fulfill()
            })
            workflowFinished = true
        }
        await fulfillment(of: [reclaimStarted,delivered],timeout: 2)
        XCTAssertFalse(workflowFinished)
        release?.resume()
        try await job.value
        XCTAssertTrue(reclaimFinished); XCTAssertTrue(workflowFinished)
    }

    @MainActor func testProviderFailureStillFinishesOwnedReceipt() async {
        enum ProviderError: Error { case unavailable }
        let reclaimStarted = expectation(description: "reclaim started after provider failure")
        let failed = expectation(description: "provider failed")
        var release: CheckedContinuation<Void,Never>?
        var reclaimed = false, workflowFinished = false
        let job = Task {
            do {
                try await SavedDelivery.run(reclaim: {
                    await withCheckedContinuation { release = $0; reclaimStarted.fulfill() }
                    reclaimed = true
                }, deliver: { failed.fulfill(); throw ProviderError.unavailable })
                XCTFail("Provider failure must remain visible")
            } catch { XCTAssertTrue(error is ProviderError) }
            workflowFinished = true
        }
        await fulfillment(of: [reclaimStarted,failed],timeout: 2)
        XCTAssertFalse(workflowFinished)
        release?.resume(); await job.value
        XCTAssertTrue(reclaimed); XCTAssertTrue(workflowFinished)
    }
}
