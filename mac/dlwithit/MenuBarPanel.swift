import SwiftUI

// The panel that drops down from the menu bar icon (direction B).
struct MenuBarPanel: View {
    @Environment(AppModel.self) private var model
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        let items = model.recentItems
        let now = items.filter(\.isActive)
        let recent = Array(items.filter { !$0.isActive }.prefix(4))

        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 1) {
                    Text("dlwithit").font(.headline)
                    Text(model.statusLine).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                IconButton(systemImage: "macwindow", help: "Open Window") {
                    openMainWindow()
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

            if !model.picks.isEmpty {
                Button {
                    openMainWindow()
                } label: {
                    Label(model.picks.count == 1 ? "Choose videos to download…" : "\(model.picks.count) pages waiting for you to choose videos…",
                          systemImage: "checklist")
                }
                .buttonStyle(.link)
                .padding(.horizontal, 14).padding(.bottom, 6)
            }

            if model.connection != .connected {
                Text(model.connection == .starting ? "Starting…" : "Not connected — open the window for details.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .padding(14)
            } else if now.isEmpty && recent.isEmpty {
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
                    Button("Clear") { model.clearFinished() }
                        .buttonStyle(.borderless)
                        .font(.caption)
                        .padding(.trailing, 14)
                }
                ForEach(recent) { PanelRow(item: $0) }
            }

            Divider().padding(.top, 8)
            HStack(spacing: 6) {
                Image(systemName: "folder")
                Text("Saving to \(model.saveFolderName)")
                    .lineLimit(1)
                    .truncationMode(.middle)
                Spacer()
                Button("Change") { model.chooseSaveFolder() }.buttonStyle(.borderless)
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            .padding(.horizontal, 14).padding(.vertical, 10)
        }
        .frame(width: 340)
        .animation(.default, value: model.jobs.map(\.id))
    }

    private func openMainWindow() {
        openWindow(id: "main")
        NSApp.activate()
    }

    private func header(_ title: String) -> some View {
        Text(title)
            .font(.caption.weight(.semibold))
            .foregroundStyle(.secondary)
            .padding(.horizontal, 14).padding(.top, 8).padding(.bottom, 2)
    }
}

struct PanelRow: View {
    let item: DisplayItem
    @Environment(AppModel.self) private var model

    var body: some View {
        HStack(spacing: 10) {
            Thumbnail(item: item, cornerRadius: 5)
                .frame(width: 48, height: 27)
            VStack(alignment: .leading, spacing: 3) {
                Text(item.title).font(.callout.weight(.semibold)).lineLimit(1)
                ItemProgress(item: item, size: .mini)
                DetailLine(item: item).font(.caption2).lineLimit(1)
            }
            Spacer(minLength: 6)
            if item.canConvert {
                Button("To MP4") { model.convert(item) }.controlSize(.mini)
            }
            if item.isActive {
                IconButton(systemImage: "xmark", help: "Cancel") { model.cancel(item) }
            } else if item.fileExists {
                IconButton(systemImage: "magnifyingglass", help: "Show in Finder") { model.revealInFinder(item) }
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 5)
        .contextMenu { DownloadContextMenu(item: item) }
    }
}
