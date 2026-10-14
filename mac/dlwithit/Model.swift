import SwiftUI
import Observation

// Prototype data model. Everything here is fake: the real app will get
// these items from the Python engine over the local API.

enum Source: String, CaseIterable, Identifiable {
    case youtube = "YouTube"
    case vimeo = "Vimeo"
    case instagram = "Instagram"
    case archive = "archive.org"
    case web = "Web"

    var id: String { rawValue }

    var tint: Color {
        switch self {
        case .youtube: .red
        case .vimeo: .cyan
        case .instagram: .pink
        case .archive: .gray
        case .web: .green
        }
    }
}

enum DownloadState: Equatable {
    case queued
    case downloading(progress: Double)
    case converting(progress: Double)
    case done
    case failed(message: String)

    var isActive: Bool {
        switch self {
        case .queued, .downloading, .converting: true
        default: false
        }
    }
}

struct DownloadItem: Identifiable, Equatable {
    let id = UUID()
    var title: String
    var source: Source
    var sizeMB: Double
    var format: String          // "MP4", "WebM", "JPG"…
    var isImage = false
    var thumb: Color
    var state: DownloadState
    var inQueue = true          // false once cleared from the list; still in the library

    // Shown under the title in list and gallery.
    var detail: String {
        switch state {
        case .queued:
            return "Waiting…"
        case .downloading(let p):
            let done = sizeMB * p
            let left = max(1, Int((sizeMB - done) / 1.8))
            return String(format: "%.1f of %.1f MB · 1.8 MB/s · %d sec left", done, sizeMB, left)
        case .converting(let p):
            return "Converting to MP4… \(Int(p * 100))%"
        case .done:
            return "\(source.rawValue) · \(Int(sizeMB)) MB · \(format)"
        case .failed(let message):
            return message
        }
    }

    var canConvert: Bool { state == .done && format == "WebM" }
}

enum ViewMode: String {
    case list, gallery
}

enum SidebarFilter: Hashable {
    case all, downloading, completed, attention
    case source(Source)

    var title: String {
        switch self {
        case .all: "All"
        case .downloading: "Downloading"
        case .completed: "Completed"
        case .attention: "Needs Attention"
        case .source(let s): s.rawValue
        }
    }

    func matches(_ item: DownloadItem) -> Bool {
        switch self {
        case .all: true
        case .downloading: item.state.isActive
        case .completed: item.state == .done
        case .attention: if case .failed = item.state { true } else { false }
        case .source(let s): item.source == s
        }
    }
}

@MainActor
@Observable
final class DownloadStore {
    var items: [DownloadItem] = DownloadStore.sampleItems
    var showAddLink = false     // UI state: the toolbar's Download Link popover

    init() {
        // Fake the engine's progress events so the bars move.
        Task { [weak self] in
            while true {
                try? await Task.sleep(for: .milliseconds(150))
                self?.tick()
            }
        }
    }

    var queueItems: [DownloadItem] { items.filter(\.inQueue) }
    var activeCount: Int { items.filter { $0.state.isActive && $0.state != .queued }.count }
    var queuedCount: Int { items.filter { $0.state == .queued }.count }
    var hasFinishedInQueue: Bool { items.contains { $0.inQueue && !$0.state.isActive } }

    var statusLine: String {
        if activeCount == 0 && queuedCount == 0 { return "Nothing downloading" }
        var parts: [String] = []
        if activeCount > 0 { parts.append("\(activeCount) downloading") }
        if queuedCount > 0 { parts.append("\(queuedCount) queued") }
        return parts.joined(separator: " · ")
    }

    func count(_ filter: SidebarFilter) -> Int { items.filter(filter.matches).count }

    // Removes finished and failed rows from the list. The library (gallery) keeps them.
    func clearFinished() {
        for i in items.indices where !items[i].state.isActive {
            items[i].inQueue = false
        }
    }

    func removeFromList(_ id: DownloadItem.ID) {
        if let i = items.firstIndex(where: { $0.id == id }) { items[i].inQueue = false }
    }

    func removeFromLibrary(_ id: DownloadItem.ID) {
        items.removeAll { $0.id == id }
    }

    func cancel(_ id: DownloadItem.ID) {
        items.removeAll { $0.id == id }
    }

    func retry(_ id: DownloadItem.ID) {
        if let i = items.firstIndex(where: { $0.id == id }) { items[i].state = .downloading(progress: 0) }
    }

    func convert(_ id: DownloadItem.ID) {
        if let i = items.firstIndex(where: { $0.id == id }) { items[i].state = .converting(progress: 0) }
    }

    // Prototype only: put the sample data back so the progress bars run again.
    func resetDemo() {
        items = DownloadStore.sampleItems
    }

    func add(link: String) {
        let host = URL(string: link)?.host() ?? link
        let item = DownloadItem(title: host, source: .web, sizeMB: 40, format: "MP4",
                                thumb: .indigo, state: .downloading(progress: 0))
        items.insert(item, at: 0)
    }

    private func tick() {
        var running = 0
        for i in items.indices {
            switch items[i].state {
            case .downloading(let p):
                running += 1
                let next = p + 0.0025
                if next >= 1 {
                    items[i].state = items[i].format == "WebM" ? .converting(progress: 0) : .done
                    if items[i].format == "WebM" { items[i].format = "MP4" }
                } else {
                    items[i].state = .downloading(progress: next)
                }
            case .converting(let p):
                running += 1
                let next = p + 0.006
                items[i].state = next >= 1 ? .done : .converting(progress: next)
                if next >= 1 { items[i].format = "MP4" }
            default:
                break
            }
        }
        // Start the next queued item when a slot frees up (the real app runs two at once).
        if running < 2, let q = items.firstIndex(where: { $0.state == .queued }) {
            items[q].state = .downloading(progress: 0)
        }
    }

    static let sampleItems: [DownloadItem] = [
        DownloadItem(title: "Apollo 11: Launch from Pad 39A", source: .youtube, sizeMB: 29.6, format: "MP4",
                     thumb: Color(red: 0.24, green: 0.35, blue: 0.50), state: .downloading(progress: 0.42)),
        DownloadItem(title: "Symphony in Motion (1947)", source: .archive, sizeMB: 66, format: "WebM",
                     thumb: Color(red: 0.54, green: 0.43, blue: 0.23), state: .converting(progress: 0.68)),
        DownloadItem(title: "Holiday in Hawaii", source: .archive, sizeMB: 120, format: "MP4",
                     thumb: Color(red: 0.36, green: 0.49, blue: 0.55), state: .queued),
        DownloadItem(title: "reMarkable — Paper Pro", source: .vimeo, sizeMB: 26, format: "MP4",
                     thumb: Color(red: 0.36, green: 0.42, blue: 0.37), state: .done),
        DownloadItem(title: "The Growth of Plants", source: .archive, sizeMB: 48, format: "WebM",
                     thumb: Color(red: 0.31, green: 0.43, blue: 0.23), state: .done),
        DownloadItem(title: "instagram.com/p/Dae8b-tu-eV", source: .instagram, sizeMB: 0, format: "MP4",
                     thumb: Color(red: 0.48, green: 0.29, blue: 0.37),
                     state: .failed(message: "This post may be private or removed.")),
        // Older downloads: already cleared from the list, still in the library.
        DownloadItem(title: "Saturn V stage separation", source: .youtube, sizeMB: 112, format: "MP4",
                     thumb: Color(red: 0.18, green: 0.24, blue: 0.33), state: .done, inQueue: false),
        DownloadItem(title: "Prelinger: Design for Dreaming", source: .archive, sizeMB: 66, format: "MP4",
                     thumb: Color(red: 0.60, green: 0.48, blue: 0.36), state: .done, inQueue: false),
        DownloadItem(title: "Earthrise, Apollo 8", source: .web, sizeMB: 4.2, format: "JPG", isImage: true,
                     thumb: Color(red: 0.20, green: 0.27, blue: 0.36), state: .done, inQueue: false),
        DownloadItem(title: "Hubble — Pillars of Creation", source: .web, sizeMB: 9.8, format: "JPG", isImage: true,
                     thumb: Color(red: 0.42, green: 0.31, blue: 0.23), state: .done, inQueue: false),
        DownloadItem(title: "Studio reel 2026", source: .vimeo, sizeMB: 210, format: "MP4",
                     thumb: Color(red: 0.25, green: 0.30, blue: 0.42), state: .done, inQueue: false),
        DownloadItem(title: "Type in motion — reference", source: .instagram, sizeMB: 12, format: "MP4",
                     thumb: Color(red: 0.45, green: 0.35, blue: 0.50), state: .done, inQueue: false),
    ]
}
