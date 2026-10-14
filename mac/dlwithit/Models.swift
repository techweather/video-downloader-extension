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

    var isActive: Bool { state.isActive }
    var isFailed: Bool { state == .failed }

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
                if !fileExists { return "\(source) · File moved or deleted" }
                if let size = Self.fileSize(path) { parts.append(size) }
                let ext = (path as NSString).pathExtension.uppercased()
                if !ext.isEmpty { parts.append(ext) }
            }
            return parts.joined(separator: " · ")
        default:
            return statusText
        }
    }

    private static func fileSize(_ path: String) -> String? {
        guard let bytes = (try? FileManager.default.attributesOfItem(atPath: path))?[.size] as? Int64 else {
            return nil
        }
        return ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
    }
}

enum ViewMode: String {
    case list, gallery
}

enum SidebarFilter: Hashable {
    case all, downloading, completed, attention
    case source(String)

    var title: String {
        switch self {
        case .all: "All"
        case .downloading: "Downloading"
        case .completed: "Completed"
        case .attention: "Needs Attention"
        case .source(let s): s
        }
    }

    func matches(_ item: DisplayItem) -> Bool {
        switch self {
        case .all: true
        case .downloading: item.isActive
        case .completed: item.state == .done || item.state == .skipped
        case .attention: item.state == .failed
        case .source(let s): item.source == s
        }
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
