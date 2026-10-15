import QuickLookThumbnailing
import SwiftUI

/// Thumbnail for a download: the downloaded file itself once it exists (via Quick Look),
/// otherwise the site's thumbnail URL, otherwise a tinted placeholder.
///
/// The frame's shape comes from whoever places it; the picture is laid over the frame and
/// clipped, so a tall or wide image can never push past its slot. `.fill` crops to the
/// frame; `.fit` shows the whole picture, letterboxed.
struct Thumbnail: View {
    let item: DisplayItem
    var cornerRadius: CGFloat = 7
    var contentMode: ContentMode = .fill

    @State private var fileImage: NSImage?

    var body: some View {
        RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
            .fill(background)
            .overlay { picture }
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
            .task(id: item.fileExists ? item.filePath : nil) {
                fileImage = await ThumbnailCache.shared.image(for: item.fileExists ? item.filePath : nil)
            }
    }

    private var background: AnyShapeStyle {
        contentMode == .fit
            ? AnyShapeStyle(Color.black.opacity(0.35))
            : AnyShapeStyle(sourceTint(item.source).opacity(0.35).gradient)
    }

    @ViewBuilder private var picture: some View {
        if let fileImage {
            Image(nsImage: fileImage).resizable().aspectRatio(contentMode: contentMode)
        } else if let url = item.thumbnailURL {
            AsyncImage(url: url) { phase in
                if let image = phase.image {
                    image.resizable().aspectRatio(contentMode: contentMode)
                } else {
                    placeholderGlyph
                }
            }
        } else {
            placeholderGlyph
        }
    }

    private var placeholderGlyph: some View {
        Image(systemName: item.isImage ? "photo" : "play.fill")
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(.white.opacity(0.75))
    }
}

/// Quick Look thumbnails of downloaded files, generated once per path.
@MainActor
final class ThumbnailCache {
    static let shared = ThumbnailCache()
    private var images: [String: NSImage] = [:]

    func image(for path: String?) async -> NSImage? {
        guard let path else { return nil }
        if let cached = images[path] { return cached }
        let request = QLThumbnailGenerator.Request(
            fileAt: URL(fileURLWithPath: path),
            size: CGSize(width: 320, height: 180),
            scale: NSScreen.main?.backingScaleFactor ?? 2,
            representationTypes: .thumbnail)
        guard let rep = try? await QLThumbnailGenerator.shared.generateBestRepresentation(for: request) else {
            return nil
        }
        images[path] = rep.nsImage
        return rep.nsImage
    }
}

// Detail line under a title: red with a warning icon when failed.
struct DetailLine: View {
    let item: DisplayItem

    var body: some View {
        if item.isFailed {
            Label(item.detail, systemImage: "exclamationmark.triangle.fill")
                .foregroundStyle(.red)
        } else {
            Text(item.detail)
                .foregroundStyle(.secondary)
                .monospacedDigit()
        }
    }
}

struct ItemProgress: View {
    let item: DisplayItem
    var size: ControlSize = .small

    var body: some View {
        switch item.state {
        case .queued:
            ProgressView(value: 0).controlSize(size)
        case .preparing, .merging:
            ProgressView().progressViewStyle(.linear).controlSize(size)
        case .converting:
            if let p = item.progress {
                ProgressView(value: p).controlSize(size).tint(.purple)
            } else {
                ProgressView().progressViewStyle(.linear).controlSize(size).tint(.purple)
            }
        case .downloading:
            if let p = item.progress {
                ProgressView(value: p).controlSize(size)
            } else {
                ProgressView().progressViewStyle(.linear).controlSize(size)
            }
        default:
            EmptyView()
        }
    }
}

struct DownloadRow: View {
    let item: DisplayItem
    @Environment(AppModel.self) private var model

    var body: some View {
        HStack(spacing: 12) {
            Thumbnail(item: item)
                .frame(width: 80, height: 45)

            VStack(alignment: .leading, spacing: 5) {
                Text(item.title)
                    .font(.headline)
                    .lineLimit(1)
                ItemProgress(item: item)
                DetailLine(item: item)
                    .font(.caption)
                    .lineLimit(1)
            }

            Spacer(minLength: 8)
            actions
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
        .onTapGesture(count: 2) { model.open(item) }
        .contextMenu { DownloadContextMenu(item: item) }
    }

    @ViewBuilder private var actions: some View {
        HStack(spacing: 6) {
            if item.canConvert {
                Button("Convert to MP4") { model.convert(item) }
                    .controlSize(.small)
            }
            if item.isFailed && item.origin == .job {
                IconButton(systemImage: "info", help: "Error Details") { model.showErrorDetails(item) }
            }
            if item.isFailed || item.state == .cancelled {
                Button("Retry") { model.retry(item) }
                    .controlSize(.small)
            }
            if item.isActive {
                IconButton(systemImage: "xmark", help: "Cancel") { model.cancel(item) }
            } else if item.fileExists {
                IconButton(systemImage: "magnifyingglass", help: "Show in Finder") { model.revealInFinder(item) }
            }
        }
    }
}

struct IconButton: View {
    let systemImage: String
    let help: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: systemImage)
                .font(.system(size: 11, weight: .bold))
                .frame(width: 22, height: 22)
                .contentShape(Circle())
        }
        .buttonStyle(.borderless)
        .background(.quaternary, in: Circle())
        .foregroundStyle(.secondary)
        .help(help)
        .accessibilityLabel(help)
    }
}

struct DownloadContextMenu: View {
    let item: DisplayItem
    @Environment(AppModel.self) private var model

    var body: some View {
        if item.fileExists {
            Button("Open") { model.open(item) }
            Button("Show in Finder") { model.revealInFinder(item) }
        }
        if item.canConvert {
            Button("Convert to MP4") { model.convert(item) }
        }
        if item.url != nil {
            Button("Copy Original Link") { model.copyLink(item) }
        }
        if item.origin == .job && (item.isFailed || item.state == .cancelled) {
            Button("Retry") { model.retry(item) }
        }
        if item.origin == .job && item.isFailed {
            Button("Error Details…") { model.showErrorDetails(item) }
        }
        Divider()
        if item.isActive {
            Button("Cancel Download") { model.cancel(item) }
        } else if item.origin == .library {
            Button("Remove from Library") { model.remove(item) }
        } else {
            Button("Remove from List") { model.remove(item) }
        }
    }
}

struct GalleryCard: View {
    let item: DisplayItem
    @Environment(AppModel.self) private var model

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Thumbnail(item: item, cornerRadius: 10)
                .aspectRatio(16 / 9, contentMode: .fit)
                .overlay(alignment: .bottom) { progressOverlay }
                .overlay(alignment: .topTrailing) { badge }
                .opacity(item.fileExists || item.isActive ? 1 : 0.55)

            VStack(alignment: .leading, spacing: 1) {
                Text(item.title)
                    .font(.callout.weight(.semibold))
                    .lineLimit(1)
                DetailLine(item: item)
                    .font(.caption)
                    .lineLimit(1)
            }
        }
        .contentShape(Rectangle())
        .onTapGesture(count: 2) { model.open(item) }
        .contextMenu { DownloadContextMenu(item: item) }
    }

    @ViewBuilder private var badge: some View {
        let text: String? = item.fileCount > 1 ? "\(item.fileCount) files"
            : item.canConvert ? "WebM" : nil
        if let text {
            Text(text)
                .font(.caption2.weight(.semibold))
                .padding(.horizontal, 7).padding(.vertical, 2)
                .background(.black.opacity(0.5), in: Capsule())
                .foregroundStyle(.white)
                .padding(6)
        }
    }

    @ViewBuilder private var progressOverlay: some View {
        if item.isActive {
            HStack(spacing: 6) {
                ItemProgress(item: item, size: .mini)
                    .tint(.white)
                if let p = item.progress {
                    Text("\(Int(p * 100))%")
                        .font(.caption2.weight(.semibold))
                        .monospacedDigit()
                        .foregroundStyle(.white)
                }
            }
            .padding(.horizontal, 8).padding(.vertical, 6)
            .background(.ultraThinMaterial.opacity(0.9))
            .environment(\.colorScheme, .dark)
            .clipShape(UnevenRoundedRectangle(bottomLeadingRadius: 10, bottomTrailingRadius: 10))
        }
    }
}
