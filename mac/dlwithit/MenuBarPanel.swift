import SwiftUI

// The panel that drops down from the menu bar icon (direction B).
struct MenuBarPanel: View {
    @Environment(DownloadStore.self) private var store
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        let queue = store.queueItems
        let now = queue.filter { $0.state.isActive }
        let recent = Array(queue.filter { !$0.state.isActive }.prefix(4))

        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 1) {
                    Text("dlwithit").font(.headline)
                    Text(store.statusLine).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                IconButton(systemImage: "macwindow", help: "Open Window") {
                    openWindow(id: "main")
                    NSApp.activate(ignoringOtherApps: true)
                }
                SettingsLink {
                    Image(systemName: "gearshape")
                        .font(.system(size: 11, weight: .bold))
                        .frame(width: 22, height: 22)
                }
                .buttonStyle(.borderless)
                .background(.quaternary, in: Circle())
                .foregroundStyle(.secondary)
                .help("Settings")
            }
            .padding(.horizontal, 14).padding(.top, 12).padding(.bottom, 8)

            if now.isEmpty && recent.isEmpty {
                Text("Right-click a video or image in your browser and choose dlwithit.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .padding(14)
            }

            if !now.isEmpty {
                header("Now")
                ForEach(now) { PanelRow(item: $0) }
            }

            if !recent.isEmpty {
                HStack {
                    header("Recent")
                    Spacer()
                    Button("Clear") { withAnimation { store.clearFinished() } }
                        .buttonStyle(.borderless)
                        .font(.caption)
                        .padding(.trailing, 14)
                }
                ForEach(recent) { PanelRow(item: $0) }
            }

            Divider().padding(.top, 8)
            HStack(spacing: 6) {
                Image(systemName: "folder")
                Text("Saving to Downloads/dlwithit")
                Spacer()
                Button("Change") {}.buttonStyle(.borderless)
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            .padding(.horizontal, 14).padding(.vertical, 10)
        }
        .frame(width: 340)
        .animation(.default, value: store.queueItems.map(\.id))
    }

    private func header(_ title: String) -> some View {
        Text(title)
            .font(.caption.weight(.semibold))
            .foregroundStyle(.secondary)
            .padding(.horizontal, 14).padding(.top, 8).padding(.bottom, 2)
    }
}

struct PanelRow: View {
    let item: DownloadItem
    @Environment(DownloadStore.self) private var store

    var body: some View {
        HStack(spacing: 10) {
            Thumbnail(item: item, cornerRadius: 5)
                .frame(width: 48, height: 27)
            VStack(alignment: .leading, spacing: 3) {
                Text(item.title).font(.callout.weight(.semibold)).lineLimit(1)
                switch item.state {
                case .downloading(let p): ProgressView(value: p).controlSize(.mini)
                case .converting(let p): ProgressView(value: p).controlSize(.mini).tint(.purple)
                default: EmptyView()
                }
                DetailLine(item: item).font(.caption2).lineLimit(1)
            }
            Spacer(minLength: 6)
            if item.canConvert {
                Button("To MP4") { store.convert(item.id) }.controlSize(.mini)
            }
            if item.state.isActive {
                IconButton(systemImage: "xmark", help: "Cancel") { store.cancel(item.id) }
            } else if item.state == .done {
                IconButton(systemImage: "magnifyingglass", help: "Show in Finder") {}
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 5)
        .contextMenu { DownloadContextMenu(item: item, inLibrary: false) }
    }
}
