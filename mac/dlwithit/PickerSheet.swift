import SwiftUI

/// Choose which videos to download from a page or playlist with several of them.
struct PickerSheet: View {
    let pick: Pick
    @Environment(AppModel.self) private var model
    @State private var selected: Set<Int> = []
    @State private var initialised = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                Text(pick.videos.count == 1 ? "1 video found" : "\(pick.videos.count) videos found")
                    .font(.title3.weight(.semibold))
                Text(pick.pageTitle)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
            .padding([.horizontal, .top], 20)
            .padding(.bottom, 12)

            List {
                ForEach(Array(pick.videos.enumerated()), id: \.offset) { index, video in
                    PickRow(video: video, isOn: binding(for: index))
                }
            }
            .listStyle(.inset)
            .frame(minHeight: 240)

            HStack {
                Button(selected.count == pick.videos.count ? "Select None" : "Select All") {
                    selected = selected.count == pick.videos.count ? [] : Set(pick.videos.indices)
                }
                Spacer()
                Button("Cancel", role: .cancel) { model.dismiss(pick) }
                    .keyboardShortcut(.cancelAction)
                Button(selected.count == 1 ? "Download 1 Video" : "Download \(selected.count) Videos") {
                    model.resolve(pick, indices: selected.sorted())
                }
                .keyboardShortcut(.defaultAction)
                .disabled(selected.isEmpty)
            }
            .padding(20)
        }
        .frame(width: 560, height: 480)
        .onAppear {
            // Everything starts selected; more videos arriving from a second scan join selected too.
            if !initialised {
                selected = Set(pick.videos.indices)
                initialised = true
            }
        }
        .onChange(of: pick.videos.count) { old, new in
            selected.formUnion(old..<new)
        }
    }

    private func binding(for index: Int) -> Binding<Bool> {
        Binding(
            get: { selected.contains(index) },
            set: { on in
                if on { selected.insert(index) } else { selected.remove(index) }
            })
    }
}

private struct PickRow: View {
    let video: PickVideo
    @Binding var isOn: Bool

    var body: some View {
        HStack(spacing: 12) {
            Toggle("", isOn: $isOn)
                .labelsHidden()
                .toggleStyle(.checkbox)
            RoundedRectangle(cornerRadius: 6, style: .continuous)
                .fill(.quaternary)
                .overlay {
                    if let thumb = video.thumbnail.flatMap(URL.init(string:)) {
                        AsyncImage(url: thumb) { $0.resizable().scaledToFill() } placeholder: { Color.clear }
                    } else {
                        Image(systemName: "play.fill").foregroundStyle(.secondary)
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                .frame(width: 72, height: 40)
            VStack(alignment: .leading, spacing: 2) {
                Text(video.title?.isEmpty == false ? video.title! : video.url)
                    .lineLimit(1)
                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
        }
        .contentShape(Rectangle())
        .onTapGesture { isOn.toggle() }
    }

    private var subtitle: String {
        var parts: [String] = []
        if let d = video.duration, d > 0 {
            let f = DateComponentsFormatter()
            f.allowedUnits = d >= 3600 ? [.hour, .minute, .second] : [.minute, .second]
            f.zeroFormattingBehavior = .pad
            if let s = f.string(from: d) { parts.append(s) }
        }
        if let u = video.uploader, !u.isEmpty { parts.append(u) }
        parts.append(URL(string: video.url)?.host() ?? video.url)
        return parts.joined(separator: " · ")
    }
}
