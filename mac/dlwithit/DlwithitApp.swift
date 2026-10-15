import SwiftUI
import UserNotifications

@main
struct DlwithitApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @AppStorage(Prefs.showMenuBar) private var showMenuBar = true

    private var model: AppModel { appDelegate.model }

    var body: some Scene {
        Window("dlwithit", id: "main") {
            MainWindow()
                .environment(model)
                .frame(minWidth: 620, minHeight: 420)
                .background(WindowOpener(model: model))
                // dlwithit://wake comes from the extension when it finds the app closed;
                // launching is all it needs.
                .onOpenURL { _ in }
        }
        .defaultSize(width: 860, height: 580)
        .commands {
            CommandGroup(after: .newItem) {
                Button("Download Link…") { model.showAddLink = true }
                    .keyboardShortcut("l")
                    .disabled(model.connection != .connected)
            }
            CommandGroup(after: .pasteboard) {
                Divider()
                Button("Clear Finished") { model.clearFinished() }
                    .keyboardShortcut("k")
                    .disabled(!model.hasFinishedInList)
            }
        }

        MenuBarExtra(isInserted: $showMenuBar) {
            MenuBarPanel()
                .environment(model)
        } label: {
            // The original "deal with it" template icon from assets/, tinted by macOS.
            Image("MenuBarIcon")
                .accessibilityLabel("dlwithit")
                .background(WindowOpener(model: model))
        }
        .menuBarExtraStyle(.window)

        Settings {
            SettingsView()
                .environment(model)
        }
    }
}

/// Gives the model a way to bring the main window forward (it can't reach SwiftUI's
/// openWindow on its own). Attached to views that exist from launch.
private struct WindowOpener: View {
    let model: AppModel
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Color.clear.frame(width: 0, height: 0)
            .onAppear {
                model.onAttentionNeeded = {
                    openWindow(id: "main")
                    NSApp.activate()
                }
            }
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, UNUserNotificationCenterDelegate {
    let model = AppModel()

    private var launchedAtLogin = false

    func applicationWillFinishLaunching(_ notification: Notification) {
        if UserDefaults.standard.object(forKey: Prefs.showInDock) as? Bool == false {
            NSApp.setActivationPolicy(.accessory)
        }
        // Opened as a login item: start quietly in the menu bar, no window.
        let event = NSAppleEventManager.shared().currentAppleEvent
        launchedAtLogin = event?.eventID == kAEOpenApplication
            && event?.paramDescriptor(forKeyword: keyAEPropData)?.enumCodeValue == keyAELaunchedAsLogInItem
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        model.onJobFinished = { [weak self] job in self?.notify(job) }
        model.start()
        if launchedAtLogin {
            DispatchQueue.main.async {
                // At launch the only titled window is the main one (the menu bar panel isn't titled).
                for window in NSApp.windows where window.isVisible && window.styleMask.contains(.titled) {
                    window.close()
                }
            }
        }

        let center = UNUserNotificationCenter.current()
        center.delegate = self
        if UserDefaults.standard.object(forKey: Prefs.notify) as? Bool ?? true {
            center.requestAuthorization(options: [.alert, .sound]) { _, error in
                if let error {
                    engineLog.error("Notification permission request failed: \(error.localizedDescription, privacy: .public)")
                }
            }
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        model.shutdown()
    }

    /// Keep running in the menu bar when the window closes.
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }

    private func notify(_ job: Job) {
        guard UserDefaults.standard.object(forKey: Prefs.notify) as? Bool ?? true,
              !NSApp.isActive,
              job.state == .done || job.state == .failed else { return }
        let content = UNMutableNotificationContent()
        content.title = job.state == .done ? "Downloaded" : "Download failed"
        content.body = job.state == .done ? job.title : "\(job.title) — \(job.error ?? "something went wrong")"
        let request = UNNotificationRequest(identifier: job.id, content: content, trigger: nil)
        UNUserNotificationCenter.current().add(request) { error in
            if let error {
                engineLog.error("Couldn't post notification: \(error.localizedDescription, privacy: .public)")
            }
        }
    }

    // Show banners even while the app is frontmost (it usually isn't).
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                            willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        [.banner]
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                            didReceive response: UNNotificationResponse) async {
        await MainActor.run {
            model.onAttentionNeeded?()
        }
    }
}
