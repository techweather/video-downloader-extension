import SwiftUI

// Colour placeholder until real thumbnails come from the engine.
struct Thumbnail: View {
    let item: DownloadItem
    var cornerRadius: CGFloat = 7

    var body: some View {
        RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
            .fill(item.thumb.gradient)
            .overlay {
                Image(systemName: item.isImage ? "photo" : "play.fill")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.white.opacity(0.75))
            }
    }
}

// Detail line under a title: red with a warning icon when failed.
struct DetailLine: View {
    let item: DownloadItem

    var body: some View {
        if case .failed(let message) = item.state {
            Label(message, systemImage: "exclamationmark.triangle.fill")
                .foregroundStyle(.red)
        } else {
            Text(item.detail)
                .foregroundStyle(.secondary)
                .monospacedDigit()
        }
    }
}

struct DownloadRow: View {
    let item: DownloadItem
    @Environment(DownloadStore.self) private var store

    var body: some View {
        HStack(spacing: 12) {
            Thumbnail(item: item)
                .frame(width: 80, height: 45)

            VStack(alignment: .leading, spacing: 5) {
                Text(item.title)
                    .font(.headline)
                    .lineLimit(1)
                progress
                DetailLine(item: item)
                    .font(.caption)
                    .lineLimit(1)
            }

            Spacer(minLength: 8)
            actions
        }
        .padding(.vertical, 4)
        .contextMenu { DownloadContextMenu(item: item, inLibrary: false) }
    }

    @ViewBuilder private var progress: some View {
        switch item.state {
        case .downloading(let p):
            ProgressView(value: p).controlSize(.small)
        case .converting(let p):
            ProgressView(value: p).controlSize(.small).tint(.purple)
        case .queued:
            ProgressView(value: 0).controlSize(.small)
        default:
            EmptyView()
        }
    }

    @ViewBuilder private var actions: some View {
        HStack(spacing: 6) {
            if item.canConvert {
                Button("Convert to MP4") { store.convert(item.id) }
                    .controlSize(.small)
            }
            if case .failed = item.state {
                Button("Retry") { store.retry(item.id) }
                    .controlSize(.small)
            }
            if item.state.isActive {
                IconButton(systemImage: "xmark", help: "Cancel") { store.cancel(item.id) }
            } else if item.state == .done {
                IconButton(systemImage: "magnifyingglass", help: "Show in Finder") {}
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
    let item: DownloadItem
    let inLibrary: Bool
    @Environment(DownloadStore.self) private var store

    var body: some View {
        if item.state == .done {
            Button("Show in Finder") {}
            Button("Open") {}
        }
        if item.canConvert {
            Button("Convert to MP4") { store.convert(item.id) }
        }
        Button("Copy Original Link") {}
        Divider()
        if inLibrary {
            Button("Remove from Library") { store.removeFromLibrary(item.id) }
        } else if item.state.isActive {
            Button("Cancel Download") { store.cancel(item.id) }
        } else {
            Button("Remove from List") { store.removeFromList(item.id) }
        }
    }
}

struct GalleryCard: View {
    let item: DownloadItem

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Thumbnail(item: item, cornerRadius: 10)
                .aspectRatio(16 / 9, contentMode: .fit)
                .overlay(alignment: .bottom) { progressOverlay }
                .overlay(alignment: .topTrailing) {
                    if item.canConvert {
                        Text("WebM")
                            .font(.caption2.weight(.semibold))
                            .padding(.horizontal, 7).padding(.vertical, 2)
                            .background(.black.opacity(0.5), in: Capsule())
                            .foregroundStyle(.white)
                            .padding(6)
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))

            VStack(alignment: .leading, spacing: 1) {
                Text(item.title)
                    .font(.callout.weight(.semibold))
                    .lineLimit(1)
                DetailLine(item: item)
                    .font(.caption)
                    .lineLimit(1)
            }
        }
        .contextMenu { DownloadContextMenu(item: item, inLibrary: true) }
    }

    @ViewBuilder private var progressOverlay: some View {
        switch item.state {
        case .downloading(let p), .converting(let p):
            HStack(spacing: 6) {
                ProgressView(value: p).controlSize(.mini).tint(.white)
                Text("\(Int(p * 100))%")
                    .font(.caption2.weight(.semibold))
                    .monospacedDigit()
                    .foregroundStyle(.white)
            }
            .padding(.horizontal, 8).padding(.vertical, 6)
            .background(.ultraThinMaterial.opacity(0.9))
            .environment(\.colorScheme, .dark)
        default:
            EmptyView()
        }
    }
}
