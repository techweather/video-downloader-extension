import SwiftUI
import AppKit

struct MainWindow: View {
    @Environment(DownloadStore.self) private var store
    @AppStorage(Prefs.viewMode) private var mode: ViewMode = .list
    @State private var filter: SidebarFilter? = .all
    @State private var showQuickSettings = false

    var body: some View {
        @Bindable var store = store
        NavigationSplitView {
            Sidebar(selection: $filter)
                .navigationSplitViewColumnWidth(min: 170, ideal: 190, max: 240)
        } detail: {
            Group {
                switch mode {
                case .list: QueueList(filter: filter ?? .all)
                case .gallery: LibraryGallery(filter: filter ?? .all)
                }
            }
            .navigationTitle("dlwithit")
            .navigationSubtitle(store.statusLine)
        }
        .toolbar {
            ToolbarItem(placement: .principal) {
                Picker("View", selection: $mode) {
                    Label("List", systemImage: "list.bullet").tag(ViewMode.list)
                    Label("Gallery", systemImage: "square.grid.2x2").tag(ViewMode.gallery)
                }
                .pickerStyle(.segmented)
                .help("Switch between the download list and the library gallery")
            }
            ToolbarItem {
                Button {
                    store.showAddLink = true
                } label: {
                    Label("Download Link", systemImage: "plus")
                }
                .help("Download a link (⌘L), or just paste one with ⌘V")
                .popover(isPresented: $store.showAddLink, arrowEdge: .bottom) {
                    AddLinkPopover()
                }
            }
            ToolbarItem {
                SaveLocationMenu()
            }
            ToolbarItem {
                Button {
                    showQuickSettings.toggle()
                } label: {
                    Label("Settings", systemImage: "gearshape")
                }
                .help("Settings")
                .popover(isPresented: $showQuickSettings, arrowEdge: .bottom) {
                    QuickSettings()
                }
            }
        }
        // ⌘V anywhere in the window (outside a text field) downloads the copied link.
        .onPasteCommand(of: [.plainText, .url]) { _ in
            if let link = Clipboard.link() { store.add(link: link) }
        }
    }
}

struct Sidebar: View {
    @Binding var selection: SidebarFilter?
    @Environment(DownloadStore.self) private var store

    var body: some View {
        List(selection: $selection) {
            Section("Downloads") {
                row(.all, "tray.full")
                row(.downloading, "arrow.down.circle")
                row(.completed, "checkmark.circle")
                row(.attention, "exclamationmark.triangle")
            }
            Section("Sources") {
                ForEach(Source.allCases) { source in
                    Label {
                        Text(source.rawValue)
                    } icon: {
                        Circle().fill(source.tint).frame(width: 8, height: 8)
                    }
                    .badge(store.count(.source(source)))
                    .tag(SidebarFilter.source(source))
                }
            }
        }
    }

    private func row(_ f: SidebarFilter, _ icon: String) -> some View {
        Label(f.title, systemImage: icon)
            .badge(store.count(f))
            .tag(f)
    }
}

struct QueueList: View {
    let filter: SidebarFilter
    @Environment(DownloadStore.self) private var store

    var body: some View {
        let visible = store.queueItems.filter(filter.matches)
        let active = visible.filter { $0.state.isActive }
        let finished = visible.filter { !$0.state.isActive }

        if visible.isEmpty {
            ContentUnavailableView {
                Label("Nothing in the list", systemImage: "arrow.down.circle")
            } description: {
                Text("Right-click a video or image in your browser and choose dlwithit. Past downloads live in the Gallery.")
            }
        } else {
            List {
                if !active.isEmpty {
                    Section("In Progress") {
                        ForEach(active) { DownloadRow(item: $0) }
                    }
                }
                if !finished.isEmpty {
                    Section {
                        ForEach(finished) { DownloadRow(item: $0) }
                    } header: {
                        HStack {
                            Text("Finished")
                            Spacer()
                            Button("Clear") { withAnimation { store.clearFinished() } }
                                .buttonStyle(.borderless)
                                .font(.callout)
                                .help("Remove finished downloads from the list (⌘K). They stay in the Gallery.")
                        }
                    }
                }
            }
            .listStyle(.inset)
            .animation(.default, value: store.queueItems.map(\.id))
        }
    }
}

struct LibraryGallery: View {
    let filter: SidebarFilter
    @Environment(DownloadStore.self) private var store

    var body: some View {
        let visible = store.items.filter(filter.matches)
        if visible.isEmpty {
            ContentUnavailableView("No downloads here", systemImage: "square.grid.2x2")
        } else {
            ScrollView {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 170, maximum: 260), spacing: 16)], spacing: 18) {
                    ForEach(visible) { GalleryCard(item: $0) }
                }
                .padding(20)
            }
        }
    }
}

struct AddLinkPopover: View {
    @Environment(DownloadStore.self) private var store
    @State private var link = Clipboard.link() ?? ""
    @FocusState private var focused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Download a link")
                .font(.headline)
            TextField("https://…", text: $link)
                .textFieldStyle(.roundedBorder)
                .frame(width: 320)
                .focused($focused)
                .onSubmit(submit)
            Text("Tip: copy a link and press ⌘V in this window.")
                .font(.caption)
                .foregroundStyle(.secondary)
            HStack {
                Spacer()
                Button("Cancel") { store.showAddLink = false }
                    .keyboardShortcut(.cancelAction)
                Button("Download", action: submit)
                    .keyboardShortcut(.defaultAction)
                    .disabled(link.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(16)
        .onAppear { focused = true }
    }

    private func submit() {
        let trimmed = link.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        store.add(link: trimmed)
        store.showAddLink = false
    }
}

struct SaveLocationMenu: View {
    @AppStorage(Prefs.saveFolder) private var folder = "Downloads/dlwithit"

    var body: some View {
        Menu {
            Button("Show in Finder") {}
            Button("Choose Folder…") {}
        } label: {
            Label(folder, systemImage: "folder")
                .labelStyle(.titleAndIcon)
        }
        .help("Where downloads are saved")
    }
}

struct QuickSettings: View {
    @AppStorage(Prefs.convertWebM) private var convertWebM = true
    @AppStorage(Prefs.keepOriginal) private var keepOriginal = false
    @AppStorage(Prefs.organizeBySite) private var organizeBySite = true
    @AppStorage(Prefs.metadata) private var metadata: MetadataOption = .none

    var body: some View {
        Form {
            Section {
                Toggle("Convert WebM to MP4", isOn: $convertWebM)
                Toggle("Keep the original file", isOn: $keepOriginal)
                    .disabled(!convertWebM)
                Toggle("Organize by site", isOn: $organizeBySite)
                Picker("Metadata", selection: $metadata) {
                    ForEach(MetadataOption.allCases) { Text($0.title).tag($0) }
                }
            }
            Section {
                SettingsLink {
                    HStack {
                        Text("All Settings…")
                        Spacer()
                        Text("⌘,").foregroundStyle(.secondary)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
        .formStyle(.grouped)
        .scrollDisabled(true)
        .scrollIndicators(.never)
        .toggleStyle(.switch)
        .frame(width: 320)
        .fixedSize(horizontal: false, vertical: true)
    }
}

enum Clipboard {
    // Returns the clipboard text if it looks like a web link.
    static func link() -> String? {
        guard let text = NSPasteboard.general.string(forType: .string)?
            .trimmingCharacters(in: .whitespacesAndNewlines),
              let url = URL(string: text),
              let scheme = url.scheme, scheme.hasPrefix("http") else { return nil }
        return text
    }
}
