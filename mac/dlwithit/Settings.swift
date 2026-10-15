import ServiceManagement
import SwiftUI

// App-only preferences, kept in UserDefaults. Download settings belong to the
// engine (see EngineSettings) so the extension and app always agree on them.
enum Prefs {
    static let viewMode = "view_mode"
    static let galleryFit = "gallery_fit"
    static let sortKey = "sort_key"
    static let sortAscending = "sort_ascending"
    static let showMenuBar = "show_in_tray"
    static let showInDock = "show_in_dock"
    static let notify = "notify_when_done"
}

struct SettingsView: View {
    @Environment(AppModel.self) private var model
    @AppStorage(Prefs.showMenuBar) private var showMenuBar = true
    @AppStorage(Prefs.showInDock) private var showInDock = true
    @AppStorage(Prefs.notify) private var notify = true
    @State private var openAtLogin = SMAppService.mainApp.status == .enabled
    @State private var loginError: String?

    var body: some View {
        Form {
            Section("Downloads") {
                LabeledContent("Save to") {
                    Menu(model.saveFolderName) {
                        Button("Show in Finder") { model.showSaveFolder() }
                        Button("Choose Folder…") { model.chooseSaveFolder() }
                        if model.settings?.useCustomLocation == true {
                            Button("Use Downloads/dlwithit") { model.useDefaultSaveFolder() }
                        }
                    }
                    .fixedSize()
                }
                EngineToggle("Organize by site", key: "organize_by_platform", value: \.organizeByPlatform,
                             subtitle: "YouTube, Vimeo, Instagram… each get a folder")
                MetadataPicker()
            }
            Section("Video") {
                EngineToggle("Convert WebM to MP4 automatically", key: "encode_vp9", value: \.encodeVp9,
                             subtitle: "Plays everywhere, including Premiere and QuickTime")
                EngineToggle("Keep the original file", key: "keep_original", value: \.keepOriginal)
                    .disabled(model.settings?.encodeVp9 != true)
            }
            .disabled(model.settings == nil)

            Section("App") {
                Toggle("Show in menu bar", isOn: $showMenuBar)
                Toggle("Show in Dock", isOn: $showInDock)
                    .onChange(of: showInDock) { _, visible in DockVisibility.apply(visible) }
                Toggle(isOn: Binding(get: { openAtLogin }, set: setOpenAtLogin)) {
                    Text("Open at login")
                    if let loginError { Text(loginError).foregroundStyle(.red) }
                }
                Toggle("Notify when downloads finish", isOn: $notify)
            }

            Section("Updates") {
                LabeledContent {
                    if model.checkingForUpdates {
                        ProgressView().controlSize(.small)
                    } else if let info = model.updateInfo, info.appUpdateAvailable,
                              let url = URL(string: info.releaseUrl) {
                        Link("Get \(info.latestAppVersion)", destination: url)
                    } else {
                        Button("Check Now") { model.checkForUpdates() }
                            .disabled(model.connection != .connected)
                    }
                } label: {
                    Text("dlwithit \(model.engineVersion ?? "")")
                    Text(appUpdateLine)
                }
                LabeledContent {
                    EmptyView()
                } label: {
                    Text("Download engine")
                    Text(engineLine)
                }
            }
        }
        .formStyle(.grouped)
        .toggleStyle(.switch)
        .frame(width: 480)
        .fixedSize(horizontal: false, vertical: true)
    }

    private var appUpdateLine: String {
        guard let info = model.updateInfo else { return "Checks GitHub for a newer release" }
        if info.latestAppVersion.isEmpty { return "Couldn't reach GitHub" }
        return info.appUpdateAvailable ? "Version \(info.latestAppVersion) is available" : "Up to date"
    }

    private var engineLine: String {
        let current = model.ytdlpVersion.map { "yt-dlp \($0)" } ?? "yt-dlp"
        if let latest = model.updateInfo?.latestYtdlpVersion, !latest.isEmpty,
           latest != model.ytdlpVersion {
            return "\(current) · \(latest) arrives with the next dlwithit update"
        }
        return "\(current) · updated with the app"
    }

    private func setOpenAtLogin(_ on: Bool) {
        do {
            if on { try SMAppService.mainApp.register() } else { try SMAppService.mainApp.unregister() }
            loginError = nil
        } catch {
            loginError = error.localizedDescription
        }
        openAtLogin = SMAppService.mainApp.status == .enabled
    }
}

/// Showing or hiding the Dock icon (and the app switcher entry) while running.
enum DockVisibility {
    @MainActor
    static func apply(_ visible: Bool) {
        NSApp.setActivationPolicy(visible ? .regular : .accessory)
        if visible { NSApp.activate() }
    }
}
