import SwiftUI

// UserDefaults keys. Names match the Qt app's settings where one exists.
enum Prefs {
    static let viewMode = "view_mode"
    static let saveFolder = "save_folder"
    static let organizeBySite = "organize_by_platform"
    static let metadata = "metadata_option"
    static let convertWebM = "encode_vp9"
    static let keepOriginal = "keep_original"
    static let showMenuBar = "show_in_tray"
    static let showInDock = "show_in_dock"
    static let openAtLogin = "launch_at_login"
}

enum MetadataOption: String, CaseIterable, Identifiable {
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

struct SettingsView: View {
    @AppStorage(Prefs.saveFolder) private var folder = "Downloads/dlwithit"
    @AppStorage(Prefs.organizeBySite) private var organizeBySite = true
    @AppStorage(Prefs.metadata) private var metadata: MetadataOption = .none
    @AppStorage(Prefs.convertWebM) private var convertWebM = true
    @AppStorage(Prefs.keepOriginal) private var keepOriginal = false
    @AppStorage(Prefs.showMenuBar) private var showMenuBar = true
    @AppStorage(Prefs.showInDock) private var showInDock = true
    @AppStorage(Prefs.openAtLogin) private var openAtLogin = false

    var body: some View {
        Form {
            Section("Downloads") {
                LabeledContent("Save to") {
                    Menu(folder) {
                        Button("Show in Finder") {}
                        Button("Choose Folder…") {}
                    }
                    .fixedSize()
                }
                Toggle(isOn: $organizeBySite) {
                    Text("Organize by site")
                    Text("YouTube, Vimeo, Instagram… each get a folder")
                }
                Picker("Metadata", selection: $metadata) {
                    ForEach(MetadataOption.allCases) { Text($0.title).tag($0) }
                }
            }
            Section("Video") {
                Toggle(isOn: $convertWebM) {
                    Text("Convert WebM to MP4 automatically")
                    Text("Plays everywhere, including Premiere and QuickTime")
                }
                Toggle("Keep the original file", isOn: $keepOriginal)
                    .disabled(!convertWebM)
            }
            Section("App") {
                Toggle("Show in menu bar", isOn: $showMenuBar)
                Toggle("Show in Dock", isOn: $showInDock)
                Toggle("Open at login", isOn: $openAtLogin)
            }
            Section("Updates") {
                LabeledContent {
                    Button("Check Now") {}
                } label: {
                    Text("dlwithit 0.1 (prototype)")
                    Text("Up to date")
                }
                LabeledContent {
                    EmptyView()
                } label: {
                    Text("Download engine")
                    Text("yt-dlp 2026.8.19 · updated with the app")
                }
            }
        }
        .formStyle(.grouped)
        .toggleStyle(.switch)
        .frame(width: 480)
        .fixedSize(horizontal: false, vertical: true)
    }
}
