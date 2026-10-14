import SwiftUI

@main
struct DlwithitApp: App {
    @State private var store = DownloadStore()
    @AppStorage(Prefs.showMenuBar) private var showMenuBar = true

    var body: some Scene {
        Window("dlwithit", id: "main") {
            MainWindow()
                .environment(store)
                .frame(minWidth: 620, minHeight: 420)
        }
        .defaultSize(width: 860, height: 580)
        .commands {
            CommandGroup(after: .newItem) {
                Button("Download Link…") { store.showAddLink = true }
                    .keyboardShortcut("l")
            }
            CommandGroup(after: .pasteboard) {
                Divider()
                Button("Clear Finished") { withAnimation { store.clearFinished() } }
                    .keyboardShortcut("k")
                    .disabled(!store.hasFinishedInQueue)
            }
            CommandMenu("Prototype") {
                Button("Reset Demo Data") { store.resetDemo() }
                    .keyboardShortcut("r", modifiers: [.command, .shift])
            }
        }

        MenuBarExtra("dlwithit", systemImage: "arrow.down.circle", isInserted: $showMenuBar) {
            MenuBarPanel()
                .environment(store)
        }
        .menuBarExtraStyle(.window)

        Settings {
            SettingsView()
        }
    }
}
