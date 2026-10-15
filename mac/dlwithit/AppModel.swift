import AppKit
import Observation
import SwiftUI

/// Everything the windows show, kept in sync with the engine's event stream.
@MainActor
@Observable
final class AppModel {
    enum Connection: Equatable {
        case starting
        case connected
        case otherAppRunning
        case failed(String)
    }

    var connection: Connection = .starting
    var jobs: [Job] = []                  // in the list, newest first
    var picks: [Pick] = []
    var library: [LibraryEntry] = []
    var settings: EngineSettings?
    var ytdlpVersion: String?
    var engineVersion: String?
    var updateInfo: UpdateInfo?
    var checkingForUpdates = false

    var showAddLink = false               // the toolbar's Download Link popover
    var alert: AlertMessage?

    struct AlertMessage: Identifiable, Equatable {
        let id = UUID()
        var title: String
        var message: String
    }

    private let launcher = EngineLauncher()
    private(set) var client: EngineClient?
    private var eventsTask: Task<Void, Never>?
    private var libraryRefresh: Task<Void, Never>?
    private var sawFirstJob = false

    /// Called on job events the app should react to beyond redrawing (notifications, window).
    var onJobFinished: ((Job) -> Void)?
    var onAttentionNeeded: (() -> Void)?

    // MARK: - Connecting

    func start() {
        guard eventsTask == nil else { return }
        eventsTask = Task { await self.connectLoop() }
    }

    func retryConnection() {
        eventsTask?.cancel()
        eventsTask = nil
        connection = .starting
        start()
    }

    func shutdown() {
        eventsTask?.cancel()
        launcher.stopIfOwned(client: client)
    }

    private func connectLoop() async {
        while !Task.isCancelled {
            switch await launcher.connect() {
            case .otherAppRunning:
                connection = .otherAppRunning
                return
            case .failed(let message):
                connection = .failed(message)
                return
            case .connected(let client):
                self.client = client
                await follow(client)
                // The stream ended: the engine quit or restarted. Try again shortly.
                if Task.isCancelled { return }
                connection = .starting
                try? await Task.sleep(for: .seconds(1))
            }
        }
    }

    private func follow(_ client: EngineClient) async {
        do {
            for try await event in client.events() {
                apply(event)
            }
        } catch {
            engineLog.error("Event stream ended: \(error.localizedDescription, privacy: .public)")
        }
    }

    private func apply(_ event: EngineClient.Event) {
        switch event {
        case .snapshot(let snap):
            jobs = snap.jobs
            picks = snap.picks
            settings = snap.settings
            engineVersion = snap.version
            ytdlpVersion = snap.ytdlpVersion
            connection = .connected
            refreshLibrary()
            if !picks.isEmpty { onAttentionNeeded?() }

        case .job(let job):
            let previous = jobs.first { $0.id == job.id }
            if let i = jobs.firstIndex(where: { $0.id == job.id }) {
                jobs[i] = job
            } else if job.inList {
                jobs.insert(job, at: 0)
                if !sawFirstJob {
                    sawFirstJob = true
                    onAttentionNeeded?()
                }
            }
            if let previous, previous.state.isActive, !job.state.isActive {
                onJobFinished?(job)
                refreshLibrary()
            }

        case .jobRemoved(let id):
            jobs.removeAll { $0.id == id }

        case .pick(let pick):
            if let i = picks.firstIndex(where: { $0.id == pick.id }) {
                picks[i] = pick
            } else {
                picks.append(pick)
                onAttentionNeeded?()
            }

        case .pickClosed(let id):
            picks.removeAll { $0.id == id }

        case .settings(let s):
            settings = s
        }
    }

    // MARK: - Derived

    /// This session's downloads (the clearable list), newest first.
    var recentItems: [DisplayItem] { jobs.map(DisplayItem.init(job:)) }

    /// Everything: what's still in progress, then the library.
    var libraryItems: [DisplayItem] {
        let active = jobs.filter { $0.state.isActive }.map(DisplayItem.init(job:))
        let activeIDs = Set(active.map(\.id))
        return active + library.filter { !activeIDs.contains($0.id) }.map(DisplayItem.init(entry:))
    }

    /// What a sidebar entry contains.
    func items(in collection: Collection) -> [DisplayItem] {
        switch collection {
        case .recent: recentItems
        case .library: libraryItems
        case .downloading: libraryItems.filter(\.isActive)
        case .attention: libraryItems.filter(\.isFailed)
        case .source(let s): libraryItems.filter { $0.source == s }
        }
    }

    var activeCount: Int { jobs.filter { $0.state.isActive && $0.state != .queued }.count }
    var queuedCount: Int { jobs.filter { $0.state == .queued }.count }
    var hasFinishedInList: Bool { jobs.contains { !$0.state.isActive } }

    var statusLine: String {
        switch connection {
        case .starting: return "Starting…"
        case .otherAppRunning, .failed: return "Not connected"
        case .connected: break
        }
        if activeCount == 0 && queuedCount == 0 { return "Nothing downloading" }
        var parts: [String] = []
        if activeCount > 0 { parts.append("\(activeCount) downloading") }
        if queuedCount > 0 { parts.append("\(queuedCount) queued") }
        return parts.joined(separator: " · ")
    }

    /// Every source seen in the list or library, most used first.
    var sources: [String] {
        var counts: [String: Int] = [:]
        for item in libraryItems { counts[item.source, default: 0] += 1 }
        return counts.sorted { $0.value == $1.value ? $0.key < $1.key : $0.value > $1.value }.map(\.key)
    }

    var saveFolderName: String {
        guard let path = settings?.savePath else { return "Downloads" }
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        if path.hasPrefix(home + "/") {
            return String(path.dropFirst(home.count + 1))
        }
        return path
    }

    // MARK: - Actions

    private func perform(_ title: String, _ action: @escaping @MainActor (EngineClient) async throws -> Void) {
        guard let client else { return }
        Task {
            do {
                try await action(client)
            } catch {
                alert = AlertMessage(title: title, message: error.localizedDescription)
            }
        }
    }

    func cancel(_ item: DisplayItem) { perform("Couldn't cancel") { try await $0.post("app/jobs/\(item.id)/cancel") } }
    func retry(_ item: DisplayItem) { perform("Couldn't retry") { try await $0.post("app/jobs/\(item.id)/retry") } }
    func convert(_ item: DisplayItem) { perform("Couldn't convert") { try await $0.post("app/jobs/\(item.id)/convert") } }

    func remove(_ item: DisplayItem) {
        switch item.origin {
        case .job:
            perform("Couldn't remove") { try await $0.post("app/jobs/\(item.id)/remove") }
        case .library:
            library.removeAll { $0.id == item.id }
            perform("Couldn't remove") { try await $0.delete("app/library/\(item.id)") }
        }
    }

    func clearFinished() {
        withAnimation { jobs.removeAll { !$0.state.isActive } }
        perform("Couldn't clear the list") { try await $0.post("app/jobs/clear-finished") }
    }

    /// The failed download whose error details are showing (with Copy / Send Report).
    var errorDetailsItem: DisplayItem?

    func showErrorDetails(_ item: DisplayItem) {
        errorDetailsItem = item
    }

    func sendErrorReport(_ item: DisplayItem) async -> Bool {
        guard let client else { return false }
        do {
            try await client.post("app/jobs/\(item.id)/report")
            return true
        } catch {
            return false
        }
    }

    func addLink(_ link: String) {
        perform("Can't download that link") { try await $0.post("app/jobs", ["url": link]) }
    }

    func resolve(_ pick: Pick, indices: [Int]) {
        picks.removeAll { $0.id == pick.id }
        perform("Couldn't start those downloads") { try await $0.post("app/picks/\(pick.id)", ["indices": indices]) }
    }

    func dismiss(_ pick: Pick) {
        picks.removeAll { $0.id == pick.id }
        perform("Couldn't close the list") { try await $0.delete("app/picks/\(pick.id)") }
    }

    func updateSettings(_ changes: [String: any Sendable]) {
        perform("Couldn't change that setting") { client in
            let updated: EngineSettings = try await client.patch("app/settings", changes)
            self.settings = updated
        }
    }

    func chooseSaveFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.prompt = "Save Here"
        panel.message = "Choose where dlwithit saves downloads"
        if let path = settings?.savePath { panel.directoryURL = URL(fileURLWithPath: path) }
        guard panel.runModal() == .OK, let url = panel.url else { return }
        updateSettings(["use_custom_location": true, "custom_location": url.path])
    }

    func useDefaultSaveFolder() {
        updateSettings(["use_custom_location": false])
    }

    func showSaveFolder() {
        guard let path = settings?.savePath else { return }
        try? FileManager.default.createDirectory(atPath: path, withIntermediateDirectories: true)
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }

    func checkForUpdates() {
        guard let client, !checkingForUpdates else { return }
        checkingForUpdates = true
        Task {
            defer { checkingForUpdates = false }
            updateInfo = try? await client.get("app/updates")
        }
    }

    func refreshLibrary() {
        guard let client else { return }
        libraryRefresh?.cancel()
        libraryRefresh = Task {
            if let entries: [LibraryEntry] = try? await client.get("app/library") {
                library = entries
            }
        }
    }

    // MARK: - Files

    func revealInFinder(_ item: DisplayItem) {
        guard let path = item.filePath else { return }
        let url = URL(fileURLWithPath: path)
        if item.fileCount > 1 || !item.fileExists {
            NSWorkspace.shared.open(url.deletingLastPathComponent())
        } else {
            NSWorkspace.shared.activateFileViewerSelecting([url])
        }
    }

    func open(_ item: DisplayItem) {
        guard let path = item.filePath, item.fileExists else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }

    func copyLink(_ item: DisplayItem) {
        guard let url = item.url else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(url, forType: .string)
    }
}
