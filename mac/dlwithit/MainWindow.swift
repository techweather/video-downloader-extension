import QuickLook
import SwiftUI
import AppKit

struct MainWindow: View {
    @Environment(AppModel.self) private var model
    @AppStorage(Prefs.viewMode) private var mode: ViewMode = .list
    @State private var collection: Collection? = .recent
    @State private var showQuickSettings = false

    var body: some View {
        @Bindable var model = model
        let current = collection ?? .recent
        NavigationSplitView {
            Sidebar(selection: $collection)
                .navigationSplitViewColumnWidth(min: 170, ideal: 190, max: 240)
        } detail: {
            Group {
                switch model.connection {
                case .connected:
                    CollectionContent(collection: current, mode: mode)
                        .id(current)        // fresh selection per collection
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
            .navigationTitle(current.title)
            .navigationSubtitle(model.statusLine)
        }
        .toolbar {
            // How to show it — like Finder's view and sort buttons, on the trailing side.
            ToolbarItem {
                Picker("View", selection: $mode) {
                    Label("List", systemImage: "list.bullet").accessibilityLabel("List").tag(ViewMode.list)
                    Label("Gallery", systemImage: "square.grid.2x2").accessibilityLabel("Gallery").tag(ViewMode.gallery)
                }
                .pickerStyle(.segmented)
                .help("Show as a list or a gallery")
            }
            ToolbarItem {
                SortMenu()
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
    @Binding var selection: Collection?
    @Environment(AppModel.self) private var model

    var body: some View {
        List(selection: $selection) {
            Section {
                row(.recent, "clock")
                row(.library, "square.stack")
            }
            Section("Status") {
                row(.downloading, "arrow.down.circle")
                row(.attention, "exclamationmark.triangle")
            }
            if !model.sources.isEmpty {
                Section("Sources") {
                    ForEach(model.sources, id: \.self) { source in
                        Label {
                            Text(source)
                        } icon: {
                            Circle().fill(sourceTint(source)).frame(width: 8, height: 8)
                        }
                        .badge(model.items(in: .source(source)).count)
                        .tag(Collection.source(source))
                    }
                }
            }
        }
    }

    private func row(_ c: Collection, _ icon: String) -> some View {
        Label(c.title, systemImage: icon)
            .badge(model.items(in: c).count)
            .tag(c)
    }
}

/// Finder-style sort menu: what to sort by, then which way.
struct SortMenu: View {
    @AppStorage(Prefs.sortKey) private var key: SortKey = .date
    @AppStorage(Prefs.sortAscending) private var ascending = false

    var body: some View {
        Menu {
            Picker("Sort By", selection: Binding(
                get: { key },
                set: { new in
                    if new != key { ascending = new.defaultAscending }
                    key = new
                })) {
                ForEach(SortKey.allCases) { Text($0.title).tag($0) }
            }
            .pickerStyle(.inline)
            Picker("Order", selection: $ascending) {
                Text(orderLabels.ascending).tag(true)
                Text(orderLabels.descending).tag(false)
            }
            .pickerStyle(.inline)
        } label: {
            Label("Sort", systemImage: "arrow.up.arrow.down")
        }
        .help("Sorted by \(key.title.lowercased())")
    }

    private var orderLabels: (ascending: String, descending: String) {
        switch key {
        case .date: ("Oldest First", "Newest First")
        case .size: ("Smallest First", "Largest First")
        default: ("A to Z", "Z to A")
        }
    }
}

/// One sidebar collection, shown as a list or a gallery, in the chosen order.
struct CollectionContent: View {
    let collection: Collection
    let mode: ViewMode
    @Environment(AppModel.self) private var model
    @AppStorage(Prefs.sortKey) private var sortKey: SortKey = .date
    @AppStorage(Prefs.sortAscending) private var ascending = false
    // Shared by list and gallery, so switching views keeps what's selected.
    @State private var selection: Set<String> = []
    @FocusState private var focused: Bool

    var body: some View {
        let items = model.items(in: collection).sorted(by: sortKey, ascending: ascending)
        Group {
            if items.isEmpty {
                emptyState
            } else {
                switch mode {
                case .list: ItemList(collection: collection, items: items, selection: $selection, focus: $focused)
                case .gallery: ItemGallery(collection: collection, items: items, selection: $selection, focus: $focused)
                }
            }
        }
        // Like Finder: picking a sidebar entry or a view puts the keyboard in the content,
        // so ⌘A, Space and Return act on it straight away.
        .onAppear { focused = true }
        .onChange(of: mode) { focused = true }
    }

    @ViewBuilder private var emptyState: some View {
        switch collection {
        case .recent:
            ContentUnavailableView {
                Label("Nothing recent", systemImage: "arrow.down.circle")
            } description: {
                Text("Right-click a video or image in your browser and choose dlwithit. Everything you've downloaded is in Library.")
            }
        case .downloading:
            ContentUnavailableView("Nothing downloading", systemImage: "arrow.down.circle")
        case .attention:
            ContentUnavailableView("Nothing needs attention", systemImage: "checkmark.circle")
        default:
            ContentUnavailableView("No downloads yet", systemImage: "square.stack",
                                   description: Text("Everything you download is kept here, even after you clear Recent."))
        }
    }
}

/// The Clear button for Recent: removes finished items there; Library keeps them.
struct ClearRecentButton: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        Button("Clear") { model.clearFinished() }
            .buttonStyle(.borderless)
            .font(.callout)
            .disabled(!model.hasFinishedInList)
            .help("Clear finished downloads from Recent (⌘K). They stay in Library.")
    }
}

/// Offers to forget library entries whose files are gone, when there are any in view.
struct RemoveMissingButton: View {
    let items: [DisplayItem]
    @Environment(AppModel.self) private var model
    @State private var confirming = false

    var body: some View {
        let missing = items.filter(\.isMissing).count
        if missing > 0 {
            Button("Remove \(missing) Missing…") { confirming = true }
                .buttonStyle(.borderless)
                .font(.callout)
                .help("These files were moved off this disk or deleted.")
                .confirmationDialog(
                    "Remove \(missing) missing \(missing == 1 ? "item" : "items") from the Library?",
                    isPresented: $confirming
                ) {
                    Button("Remove", role: .destructive) { model.removeMissing() }
                } message: {
                    Text("Their files were moved off this disk or deleted, so dlwithit can't find them. Nothing on disk changes. To keep one, right-click it and choose Locate….")
                }
        }
    }
}

struct ItemList: View {
    let collection: Collection
    let items: [DisplayItem]
    @Binding var selection: Set<String>
    var focus: FocusState<Bool>.Binding
    @Environment(AppModel.self) private var model
    @State private var preview: URL?

    var body: some View {
        List(selection: $selection) {
            if collection == .recent {
                // Recent keeps what's running apart from what's done, with Clear on the latter.
                let active = items.filter(\.isActive)
                let finished = items.filter { !$0.isActive }
                if !active.isEmpty {
                    Section("In Progress") {
                        ForEach(active) { DownloadRow(item: $0).tag($0.id) }
                    }
                }
                if !finished.isEmpty {
                    Section {
                        ForEach(finished) { DownloadRow(item: $0).tag($0.id) }
                    } header: {
                        HStack {
                            Text("Finished")
                            Spacer()
                            ClearRecentButton()
                        }
                    }
                }
            } else {
                Section {
                    ForEach(items) { DownloadRow(item: $0).tag($0.id) }
                } header: {
                    HStack {
                        Text(items.count == 1 ? "1 item" : "\(items.count) items")
                        Spacer()
                        RemoveMissingButton(items: items)
                    }
                }
            }
        }
        .listStyle(.inset)
        .focused(focus)
        .animation(.default, value: items.map(\.id))
        // Right-click acts on the selection; double-click (or Return) opens.
        .contextMenu(forSelectionType: String.self) { ids in
            SelectionMenu(items: items.filter { ids.contains($0.id) })
        } primaryAction: { ids in
            items.filter { ids.contains($0.id) }.forEach(model.open)
        }
        .onKeyPress(.space) {
            preview = preview == nil ? quickLookURL(items, selected: selection) : nil
            return .handled
        }
        .onCommand(#selector(NSResponder.selectAll(_:))) {
            selection = Set(items.map(\.id))
        }
        .quickLookPreview($preview)
    }
}

/// Right-click menu for one or several selected downloads.
struct SelectionMenu: View {
    let items: [DisplayItem]
    @Environment(AppModel.self) private var model

    var body: some View {
        if items.count == 1, let item = items.first {
            DownloadContextMenu(item: item)
        } else if !items.isEmpty {
            let onDisk = items.filter(\.fileExists)
            if !onDisk.isEmpty {
                Button("Open \(onDisk.count) Items") { onDisk.forEach(model.open) }
                Button("Show \(onDisk.count) in Finder") { onDisk.forEach(model.revealInFinder) }
            }
            let active = items.filter(\.isActive)
            if !active.isEmpty {
                Button("Cancel \(active.count) Downloads") { active.forEach(model.cancel) }
            }
            let finished = items.filter { !$0.isActive }
            if !finished.isEmpty {
                Divider()
                Button(finished.first?.origin == .library ? "Remove \(finished.count) from Library"
                                                           : "Remove \(finished.count) from List") {
                    finished.forEach(model.remove)
                }
            }
        }
    }
}

struct ItemGallery: View {
    let collection: Collection
    let items: [DisplayItem]
    @Environment(AppModel.self) private var model
    @AppStorage(Prefs.galleryFit) private var fit = false
    @Binding var selection: Set<String>
    var focus: FocusState<Bool>.Binding
    @State private var anchor: String?                  // where a ⇧-click range starts
    @State private var preview: URL?
    @State private var cardFrames: [String: CGRect] = [:]
    @State private var band: CGRect?                    // the drag-to-select rectangle
    @State private var selectionBeforeBand: Set<String> = []
    @State private var hovered: String?                 // the card under the pointer
    @State private var rightClickMonitor: Any?

    var body: some View {
        GeometryReader { window in
            ScrollView {
                VStack(spacing: 0) {
                    header
                    grid
                }
                // Fill the window even when there are few cards, so empty space takes drags.
                .frame(maxWidth: .infinity, minHeight: window.size.height, alignment: .top)
                .coordinateSpace(.named(Self.space))
                // Clicks and drags that start between cards land here (cards take their own).
                .background {
                    Color.clear
                        .contentShape(Rectangle())
                        .onTapGesture { selection = []; anchor = nil }
                        .gesture(bandGesture)
                }
                .overlay(alignment: .topLeading) {
                    if let band {
                        Rectangle()
                            .fill(Color.accentColor.opacity(0.12))
                            .strokeBorder(Color.accentColor.opacity(0.6), lineWidth: 1)
                            .frame(width: band.width, height: band.height)
                            .offset(x: band.minX, y: band.minY)
                            .allowsHitTesting(false)
                    }
                }
            }
        }
        .focusable()
        .focused(focus)
        .focusEffectDisabled()
        .onKeyPress(.space) {
            preview = preview == nil ? quickLookURL(items, selected: selection) : nil
            return .handled
        }
        .onKeyPress(.return) {
            selectedItems.forEach(model.open)
            return .handled
        }
        .onKeyPress(.escape) {
            selection = []
            return .handled
        }
        .onCommand(#selector(NSResponder.selectAll(_:))) {
            selection = Set(items.map(\.id))
        }
        .quickLookPreview($preview)
        .onAppear {
            model.refreshLibrary()
            watchRightClicks()
        }
        .onDisappear {
            if let rightClickMonitor { NSEvent.removeMonitor(rightClickMonitor) }
            rightClickMonitor = nil
        }
    }

    private static let space = "gallery"

    /// Finder: right-clicking a card that isn't selected selects it before the menu opens.
    /// SwiftUI's context menu can't change the selection, so watch the click itself.
    private func watchRightClicks() {
        guard rightClickMonitor == nil else { return }
        let hovered = $hovered, selection = $selection, anchor = $anchor
        rightClickMonitor = NSEvent.addLocalMonitorForEvents(matching: [.rightMouseDown, .leftMouseDown]) { event in
            let isRightClick = event.type == .rightMouseDown || event.modifierFlags.contains(.control)
            if isRightClick, let id = hovered.wrappedValue, !selection.wrappedValue.contains(id) {
                selection.wrappedValue = [id]
                anchor.wrappedValue = id
            }
            return event
        }
    }

    private var selectedItems: [DisplayItem] { items.filter { selection.contains($0.id) } }

    private var header: some View {
        HStack(spacing: 12) {
            Text(items.count == 1 ? "1 item" : "\(items.count) items")
                .font(.callout)
                .foregroundStyle(.secondary)
            Spacer()
            if collection == .recent { ClearRecentButton() } else { RemoveMissingButton(items: items) }
            Picker("Thumbnails", selection: $fit) {
                Image(systemName: "rectangle.fill").help("Fill: crop each picture to its tile")
                    .accessibilityLabel("Fill").tag(false)
                Image(systemName: "rectangle.center.inset.filled").help("Fit: show the whole picture")
                    .accessibilityLabel("Fit").tag(true)
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .fixedSize()
        }
        .padding(.horizontal, 20)
        .padding(.top, 12)
    }

    private var grid: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 170, maximum: 260), spacing: 8)], spacing: 8) {
            ForEach(items) { item in
                GalleryCard(item: item, contentMode: fit ? .fit : .fill,
                            isSelected: selection.contains(item.id))
                    .onTapGesture(count: 2) {
                        selection = [item.id]
                        anchor = item.id
                        model.open(item)
                    }
                    .simultaneousGesture(TapGesture().onEnded { click(item) })
                    // Right-clicking a selected card acts on the whole selection, like Finder.
                    .contextMenu {
                        SelectionMenu(items: selection.contains(item.id) ? selectedItems : [item])
                    }
                    .onGeometryChange(for: CGRect.self) { $0.frame(in: .named(Self.space)) } action: {
                        cardFrames[item.id] = $0
                    }
                    .onHover { inside in
                        if inside { hovered = item.id } else if hovered == item.id { hovered = nil }
                    }
            }
        }
        .padding(.horizontal, 14)
        .padding(.bottom, 20)
    }

    /// Finder clicks: plain selects one, ⌘ adds or removes, ⇧ selects the run from the last click.
    private func click(_ item: DisplayItem) {
        focus.wrappedValue = true
        let flags = clickModifiers()
        if flags.contains(.command) {
            if selection.contains(item.id) { selection.remove(item.id) } else { selection.insert(item.id) }
            anchor = item.id
        } else if flags.contains(.shift), let anchor,
                  let from = items.firstIndex(where: { $0.id == anchor }),
                  let to = items.firstIndex(where: { $0.id == item.id }) {
            selection.formUnion(items[min(from, to)...max(from, to)].map(\.id))
        } else {
            selection = [item.id]
            anchor = item.id
        }
    }

    /// Drag on empty space to draw a rectangle; every card it touches is selected.
    /// Holding ⌘ or ⇧ adds to what was already selected.
    private var bandGesture: some Gesture {
        DragGesture(minimumDistance: 3, coordinateSpace: .named(Self.space))
            .onChanged { drag in
                if band == nil {
                    let flags = clickModifiers()
                    selectionBeforeBand = flags.contains(.command) || flags.contains(.shift) ? selection : []
                }
                let rect = CGRect(x: min(drag.startLocation.x, drag.location.x),
                                  y: min(drag.startLocation.y, drag.location.y),
                                  width: abs(drag.location.x - drag.startLocation.x),
                                  height: abs(drag.location.y - drag.startLocation.y))
                band = rect
                let ids = Set(items.map(\.id))
                let touched = cardFrames.filter { ids.contains($0.key) && $0.value.intersects(rect) }.keys
                selection = selectionBeforeBand.union(touched)
            }
            .onEnded { _ in band = nil }
    }
}

/// Modifier keys held for the click being handled, read from the event itself.
func clickModifiers() -> NSEvent.ModifierFlags {
    NSApp.currentEvent?.modifierFlags ?? NSEvent.modifierFlags
}

/// The first selected item that has a file on disk, for Quick Look.
func quickLookURL(_ items: [DisplayItem], selected: Set<String>) -> URL? {
    items.first { selected.contains($0.id) && $0.fileExists }
        .flatMap { $0.filePath.map(URL.init(fileURLWithPath:)) }
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
                EngineToggle("Convert WebM to MP4 automatically", key: "encode_vp9", value: \.encodeVp9)
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
