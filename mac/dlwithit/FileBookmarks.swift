import Foundation

/// Remembers each downloaded file the way a Finder alias does, so the Library can follow it
/// when it's moved or renamed on the same disk. Kept in
/// ~/Library/Application Support/dlwithit/bookmarks.plist, keyed by download id.
@MainActor
final class FileBookmarks {
    static let shared = FileBookmarks()

    private var bookmarks: [String: Data]
    private let storeURL: URL
    private var dirty = false

    private init() {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appending(path: "dlwithit", directoryHint: .isDirectory)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        storeURL = dir.appending(path: "bookmarks.plist")
        bookmarks = (try? Data(contentsOf: storeURL))
            .flatMap { try? PropertyListDecoder().decode([String: Data].self, from: $0) } ?? [:]
    }

    /// Start tracking a file that's where we expect it (no-op if already tracked).
    func remember(id: String, path: String) {
        guard bookmarks[id] == nil,
              let data = try? URL(fileURLWithPath: path).bookmarkData() else { return }
        bookmarks[id] = data
        dirty = true
    }

    /// Where a tracked file is now, if macOS can still find it.
    func currentPath(id: String) -> String? {
        guard let data = bookmarks[id] else { return nil }
        var stale = false
        guard let url = try? URL(resolvingBookmarkData: data, bookmarkDataIsStale: &stale),
              FileManager.default.fileExists(atPath: url.path) else { return nil }
        if stale, let fresh = try? url.bookmarkData() {
            bookmarks[id] = fresh
            dirty = true
        }
        return url.path
    }

    /// Track a file at a new location (after Locate…).
    func replace(id: String, path: String) {
        bookmarks[id] = nil
        remember(id: id, path: path)
    }

    func forget(ids: [String]) {
        for id in ids where bookmarks.removeValue(forKey: id) != nil { dirty = true }
    }

    func save() {
        guard dirty, let data = try? PropertyListEncoder().encode(bookmarks) else { return }
        try? data.write(to: storeURL, options: .atomic)
        dirty = false
    }
}
