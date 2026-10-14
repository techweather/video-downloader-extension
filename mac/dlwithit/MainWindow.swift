import SwiftUI
import AppKit

struct MainWindow: View {
    @Environment(AppModel.self) private var model
    @AppStorage(Prefs.viewMode) private var mode: ViewMode = .list
    @State private var filter: SidebarFilter? = .all
    @State private var showQuickSettings = false

    var body: some View {
        @Bindable var model = model
        NavigationSplitView {
            Sidebar(selection: $filter)
                .navigationSplitViewColumnWidth(min: 170, ideal: 190, max: 240)
        } detail: {
            Group {
                switch model.connection {
                case .connected:
                    switch mode {
                    case .list: QueueList(filter: filter ?? .all)
                    case .gallery: LibraryGallery(filter: filter ?? .all)
                    }
                case .starting:
                    ProgressView("Starting the download engine…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                case .otherAppRunning:
                    ContentUnavailableView {
                        Label("The old dlwithit is running", systemImage: "exclamationmark.triangle")
                    } description: {
                        Text("Quit the other copy of dlwithit (its icon is in the menu bar), then try again.")
                    } actions: {
                        Button("Try Again") { model.retryConnection() }
                    }
                case .failed(let message):
                    ContentUnavailableView {
                        Label("Couldn't start downloads", systemImage: "exclamationmark.triangle")
                    } description: {
                        Text(message)
                    } actions: {
                        Button("Try Again") { model.retryConnection() }
                    }
                }
            }
            .navigationTitle("dlwithit")
            .navigationSubtitle(model.statusLine)
        }
        .toolbar {
            ToolbarItem(placement: .principal) {
                Picker("View", selection: $mode) {
                    Label("List", systemImage: "list.bullet").tag(ViewMode.list)
                    Label("Gallery", systemImage: "square.grid.2x2").tag(ViewMode.gallery)
                }
                .pickerStyle(.segmented)
                .help("Switch between the download list and the gallery of everything you've downloaded")
            }
            ToolbarItem {
                Button {
                    model.showAddLink = true
                } label: {
                    Label("Download Link", systemImage: "plus")
                }
                .help("Download a link (⌘L), or just paste one with ⌘V")
                .disabled(model.connection != .connected)
                .popover(isPresented: $model.showAddLink, arrowEdge: .bottom) {
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
            if let link = Clipboard.link() { model.addLink(link) }
        }
        .sheet(item: Binding(get: { model.picks.first }, set: { _ in })) { pick in
            PickerSheet(pick: pick)
        }
        .sheet(item: $model.errorDetailsItem) { item in
            ErrorDetailsSheet(item: item)
        }
        .alert(item: $model.alert) { alert in
            Alert(title: Text(alert.title), message: Text(alert.message))
        }
    }
}

struct Sidebar: View {
    @Binding var selection: SidebarFilter?
    @Environment(AppModel.self) private var model

    var body: some View {
        let items = model.galleryItems
        List(selection: $selection) {
            Section("Downloads") {
                row(.all, "tray.full", items)
                row(.downloading, "arrow.down.circle", items)
                row(.completed, "checkmark.circle", items)
                row(.attention, "exclamationmark.triangle", items)
            }
            if !model.sources.isEmpty {
                Section("Sources") {
                    ForEach(model.sources, id: \.self) { source in
                        Label {
                            Text(source)
                        } icon: {
                            Circle().fill(sourceTint(source)).frame(width: 8, height: 8)
                        }
                        .badge(items.filter { $0.source == source }.count)
                        .tag(SidebarFilter.source(source))
                    }
                }
            }
        }
    }

    private func row(_ f: SidebarFilter, _ icon: String, _ items: [DisplayItem]) -> some View {
        Label(f.title, systemImage: icon)
            .badge(items.filter(f.matches).count)
            .tag(f)
    }
}

struct QueueList: View {
    let filter: SidebarFilter
    @Environment(AppModel.self) private var model

    var body: some View {
        let visible = model.listItems.filter(filter.matches)
        let active = visible.filter(\.isActive)
        let finished = visible.filter { !$0.isActive }

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
                            Button("Clear") { model.clearFinished() }
                                .buttonStyle(.borderless)
                                .font(.callout)
                                .help("Remove finished downloads from the list (⌘K). They stay in the Gallery.")
                        }
                    }
                }
            }
            .listStyle(.inset)
            .animation(.default, value: model.jobs.map(\.id))
        }
    }
}

struct LibraryGallery: View {
    let filter: SidebarFilter
    @Environment(AppModel.self) private var model

    var body: some View {
        let visible = model.galleryItems.filter(filter.matches)
        Group {
            if visible.isEmpty {
                ContentUnavailableView("No downloads here", systemImage: "square.grid.2x2",
                                       description: Text("Everything you download shows up here, even after you clear the list."))
            } else {
                ScrollView {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 170, maximum: 260), spacing: 16)], spacing: 18) {
                        ForEach(visible) { GalleryCard(item: $0) }
                    }
                    .padding(20)
                }
            }
        }
        .onAppear { model.refreshLibrary() }
    }
}

struct AddLinkPopover: View {
    @Environment(AppModel.self) private var model
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
                Button("Cancel") { model.showAddLink = false }
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
        model.addLink(trimmed)
        model.showAddLink = false
    }
}

struct SaveLocationMenu: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        Menu {
            Button("Show in Finder") { model.showSaveFolder() }
            Button("Choose Folder…") { model.chooseSaveFolder() }
            if model.settings?.useCustomLocation == true {
                Button("Use Downloads/dlwithit") { model.useDefaultSaveFolder() }
            }
        } label: {
            HStack(spacing: 7) {
                Image(systemName: "folder")
                Text(model.saveFolderName)
            }
            .padding(.horizontal, 6)
        }
        .help(model.settings?.savePath ?? "Where downloads are saved")
    }
}

struct QuickSettings: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        Form {
            Section {
                EngineToggle("Convert WebM to MP4", key: "encode_vp9", value: \.encodeVp9)
                EngineToggle("Keep the original file", key: "keep_original", value: \.keepOriginal)
                    .disabled(model.settings?.encodeVp9 != true)
                EngineToggle("Organize by site", key: "organize_by_platform", value: \.organizeByPlatform)
                MetadataPicker()
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
        .disabled(model.settings == nil)
        .frame(width: 320)
        .fixedSize(horizontal: false, vertical: true)
        .onAppear {
            // AppKit gives the first switch keyboard focus (and a blue ring) when the
            // popover opens. Clear it; Tab still brings focus rings back for keyboard users.
            DispatchQueue.main.async { NSApp.keyWindow?.makeFirstResponder(nil) }
        }
    }
}

/// A switch bound to one of the engine's download settings.
struct EngineToggle: View {
    @Environment(AppModel.self) private var model
    let title: String
    let key: String
    let value: KeyPath<EngineSettings, Bool>
    var subtitle: String? = nil

    init(_ title: String, key: String, value: KeyPath<EngineSettings, Bool>, subtitle: String? = nil) {
        self.title = title
        self.key = key
        self.value = value
        self.subtitle = subtitle
    }

    var body: some View {
        let binding = Binding(
            get: { model.settings?[keyPath: value] ?? false },
            set: { model.updateSettings([key: $0]) })
        Toggle(isOn: binding) {
            Text(title)
            if let subtitle { Text(subtitle) }
        }
    }
}

struct MetadataPicker: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        Picker("Metadata", selection: Binding(
            get: { model.settings?.metadataOption ?? .none },
            set: { model.updateSettings(["metadata_option": $0.rawValue]) })) {
            ForEach(MetadataOption.allCases) { Text($0.title).tag($0) }
        }
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
