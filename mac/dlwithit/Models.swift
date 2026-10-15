import SwiftUI

// MARK: - What the engine sends (see core/engine.py and api/flask_server.py)

enum JobState: String, Codable {
    case queued, preparing, downloading, merging, converting
    case done, skipped, failed, cancelled

    var isActive: Bool {
        switch self {
        case .queued, .preparing, .downloading, .merging, .converting: true
        default: false
        }
    }
}

struct Job: Codable, Identifiable, Equatable {
    let id: String
    var url: String
    var pageUrl: String?
    var source: String
    var kind: String            // "image" | "video" | "direct-video"
    var title: String
    var thumbnail: String?
    var state: JobState
    var progress: Double?
    var statusText: String
    var filePath: String?
    var fileCount: Int
    var error: String?
    var errorDetail: String?
    var canConvert: Bool
    var createdAt: Double
    var finishedAt: Double?
    var inList: Bool
}

struct PickVideo: Codable, Equatable {
    var url: String
    var title: String?
    var thumbnail: String?
    var duration: Double?
    var uploader: String?
}

struct Pick: Codable, Identifiable, Equatable {
    let id: String
    var pageUrl: String
    var pageTitle: String
    var source: String
    var videos: [PickVideo]
    var fromPlaylist: Bool
}

struct LibraryEntry: Codable, Identifiable, Equatable {
    let id: String
    var url: String?
    var pageUrl: String?
    var source: String?
    var kind: String?
    var title: String?
    var thumbnail: String?
    var filePath: String?
    var fileCount: Int?
    var state: JobState
    var error: String?
    var finishedAt: Double?
    var exists: Bool
}

struct EngineSettings: Codable, Equatable {
    var encodeVp9: Bool
    var keepOriginal: Bool
    var organizeByPlatform: Bool
    var metadataOption: MetadataOption
    var useCustomLocation: Bool
    var customLocation: String
    var savePath: String
    var defaultSavePath: String
}

enum MetadataOption: String, Codable, CaseIterable, Identifiable {
    case none, embedded, sidecar
    var id: String { rawValue }
    var title: String {
        switch self {
        case .none: "None"
        case .embedded: "Embedded in file"
        case .sidecar: "Sidecar files"
        }
    }
}

struct EngineSnapshot: Codable {
    var jobs: [Job]
    var picks: [Pick]
    var settings: EngineSettings
    var version: String
    var ytdlpVersion: String?
}

struct UpdateInfo: Codable {
    var appVersion: String
    var latestAppVersion: String
    var appUpdateAvailable: Bool
    var releaseUrl: String
    var ytdlpVersion: String?
    var latestYtdlpVersion: String
}

// MARK: - What the views draw

/// One row in the list or card in the gallery, built from a live job or a library entry.
struct DisplayItem: Identifiable, Equatable {
    enum Origin: Equatable { case job, library }

    let id: String
    let origin: Origin
    var title: String
    var source: String
    var url: String?
    var thumbnailURL: URL?
    var filePath: String?
    var fileExists: Bool
    var fileCount: Int
    var isImage: Bool
    var state: JobState
    var progress: Double?
    var statusText: String
    var error: String?
    var errorDetail: String?
    var canConvert: Bool
    var date: Double            // when it finished, or when it was asked for if still going

    var isActive: Bool { state.isActive }
    var sizeBytes: Int64? { fileExists ? filePath.flatMap(FileSizeCache.size) : nil }
    /// "MP4", "PNG"… from the file name, for sorting by kind.
    var kind: String {
        let ext = ((filePath ?? url ?? "") as NSString).pathExtension.uppercased()
        return ext.isEmpty ? (isImage ? "IMAGE" : "VIDEO") : ext
    }
    var isFailed: Bool { state == .failed }
    /// Downloaded, but the file isn't where we last saw it (moved off this disk, or deleted).
    var isMissing: Bool { (state == .done || state == .skipped) && filePath != nil && !fileExists }
    /// Shown faded in list and gallery: nothing on disk to open (missing, failed, cancelled).
    var isDimmed: Bool { !fileExists && !isActive }

    init(job: Job) {
        id = job.id
        origin = .job
        title = job.title
        source = job.source
        url = job.url
        thumbnailURL = job.thumbnail.flatMap(URL.init(string:))
        filePath = job.filePath
        fileExists = job.filePath.map { FileManager.default.fileExists(atPath: $0) } ?? false
        fileCount = job.fileCount
        isImage = job.kind == "image"
        state = job.state
        progress = job.progress
        statusText = job.statusText
        error = job.error
        errorDetail = job.errorDetail
        canConvert = job.canConvert && job.state == .done
        date = job.finishedAt ?? job.createdAt
    }

    init(entry: LibraryEntry) {
        id = entry.id
        origin = .library
        title = entry.title ?? entry.url ?? "Download"
        source = entry.source ?? "Web"
        url = entry.url
        thumbnailURL = entry.thumbnail.flatMap(URL.init(string:))
        filePath = entry.filePath
        fileExists = entry.exists
        fileCount = entry.fileCount ?? 1
        isImage = entry.kind == "image"
        state = entry.state
        progress = nil
        statusText = ""
        error = entry.error
        errorDetail = nil
        canConvert = false
        date = entry.finishedAt ?? 0
    }

    /// The line under the title.
    var detail: String {
        switch state {
        case .failed:
            return error ?? "Download failed"
        case .cancelled:
            return "Cancelled"
        case .skipped:
            return "Already downloaded"
        case .done:
            if fileCount > 1 { return "\(source) · \(fileCount) files" }
            var parts = [source]
            if let path = filePath {
                if !fileExists { return "\(source) · Missing — moved or deleted" }
                if let bytes = sizeBytes {
                    parts.append(ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file))
                }
                let ext = (path as NSString).pathExtension.uppercased()
                if !ext.isEmpty { parts.append(ext) }
            }
            return parts.joined(separator: " · ")
        default:
            return statusText
        }
    }

}

/// File sizes, read from disk once per path; the list redraws several times a second.
enum FileSizeCache {
    nonisolated(unsafe) private static var sizes: [String: Int64] = [:]
    private static let lock = NSLock()

    static func size(_ path: String) -> Int64? {
        lock.lock(); defer { lock.unlock() }
        if let known = sizes[path] { return known }
        guard let bytes = (try? FileManager.default.attributesOfItem(atPath: path))?[.size] as? Int64 else {
            return nil
        }
        sizes[path] = bytes
        return bytes
    }
}

enum ViewMode: String {
    case list, gallery
}

/// What the window shows, picked in the sidebar. The List | Gallery switch only changes how.
enum Collection: Hashable {
    case recent                 // this session's downloads; Clear empties it
    case library                // everything ever downloaded
    case downloading, attention
    case source(String)

    var title: String {
        switch self {
        case .recent: "Recent"
        case .library: "Library"
        case .downloading: "Downloading"
        case .attention: "Needs Attention"
        case .source(let s): s
        }
    }
}

enum SortKey: String, CaseIterable, Identifiable {
    case date, name, size, source, kind
    var id: String { rawValue }
    var title: String {
        switch self {
        case .date: "Date Downloaded"
        case .name: "Name"
        case .size: "Size"
        case .source: "Source"
        case .kind: "Kind"
        }
    }
    /// Newest, biggest first feels natural; names and sources read A→Z.
    var defaultAscending: Bool { self == .name || self == .source || self == .kind }
}

extension Array where Element == DisplayItem {
    func sorted(by key: SortKey, ascending: Bool) -> [DisplayItem] {
        sorted { ascending ? Self.precedes($0, $1, key) : Self.precedes($1, $0, key) }
    }

    // True when a comes before b in ascending order; ties fall back to newest first.
    private static func precedes(_ a: DisplayItem, _ b: DisplayItem, _ key: SortKey) -> Bool {
        let order: ComparisonResult
        switch key {
        case .date: order = a.date < b.date ? .orderedAscending : a.date > b.date ? .orderedDescending : .orderedSame
        case .name: order = a.title.localizedStandardCompare(b.title)
        case .size:
            let x = a.sizeBytes ?? -1, y = b.sizeBytes ?? -1
            order = x < y ? .orderedAscending : x > y ? .orderedDescending : .orderedSame
        case .source: order = a.source.localizedStandardCompare(b.source)
        case .kind: order = a.kind.localizedStandardCompare(b.kind)
        }
        return order == .orderedSame ? a.date > b.date : order == .orderedAscending
    }
}

/// Dot colour for well-known sources in the sidebar.
func sourceTint(_ source: String) -> Color {
    switch source {
    case "YouTube": .red
    case "Vimeo": .cyan
    case "Instagram": .pink
    case "TikTok": .purple
    case "archive.org": .gray
    case "X": .primary
    default: .green
    }
}
