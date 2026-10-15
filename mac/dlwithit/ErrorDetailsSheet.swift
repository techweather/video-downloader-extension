import SwiftUI

/// What went wrong with a failed download, with the option to send an anonymous report.
struct ErrorDetailsSheet: View {
    let item: DisplayItem
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var sending = false
    @State private var sendFailed = false
    @State private var copied = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Label {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Couldn't download “\(item.title)”")
                        .font(.headline)
                        .lineLimit(2)
                    Text(item.error ?? "Download failed")
                        .foregroundStyle(.secondary)
                }
            } icon: {
                Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.red)
            }

            ScrollView {
                Text(details)
                    .font(.system(.caption, design: .monospaced))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(10)
            }
            .frame(height: 220)
            .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 8))

            Text("Sending a report shares this error, the link and the app version — nothing else. Your username is removed from file paths.")
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            HStack {
                Button(copied ? "Copied" : "Copy Details") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(details, forType: .string)
                    copied = true
                }
                Spacer()
                if sendFailed {
                    Text("Couldn't send — try copying instead.")
                        .font(.caption)
                        .foregroundStyle(.red)
                }
                Button("Close") { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button(sending ? "Sending…" : "Send Report") {
                    sending = true
                    Task {
                        let ok = await model.sendErrorReport(item)
                        sending = false
                        if ok { dismiss() } else { sendFailed = true }
                    }
                }
                .keyboardShortcut(.defaultAction)
                .disabled(sending)
            }
        }
        .padding(20)
        .frame(width: 520)
        .onAppear {
            // Don't open with a focus ring on Copy Details; Tab still brings rings back.
            DispatchQueue.main.async { NSApp.keyWindow?.makeFirstResponder(nil) }
        }
    }

    private var details: String {
        var text = item.errorDetail ?? item.error ?? "No details were recorded."
        if let url = item.url, !text.contains(url) { text = "URL: \(url)\n\n" + text }
        return text
    }
}
