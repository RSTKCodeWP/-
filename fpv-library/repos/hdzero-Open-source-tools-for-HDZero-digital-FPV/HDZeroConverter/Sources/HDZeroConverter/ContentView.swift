import SwiftUI
import UniformTypeIdentifiers
import AppKit

struct ContentView: View {
    @EnvironmentObject var model: ConversionModel
    @State private var dropTargeted = false

    private let controlWidth: CGFloat = 168

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            HStack(spacing: 0) {
                leftPane
                    .frame(width: 320)
                Divider()
                settingsPane
            }
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .tint(Color(red: 0.30, green: 0.36, blue: 0.95))
    }

    // MARK: Header

    private var header: some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 11, style: .continuous)
                .fill(LinearGradient(
                    colors: [Color(red: 0.36, green: 0.20, blue: 0.92),
                             Color(red: 0.13, green: 0.66, blue: 0.95)],
                    startPoint: .topLeading, endPoint: .bottomTrailing))
                .frame(width: 42, height: 42)
                .overlay(Image(systemName: "play.fill")
                    .font(.system(size: 17, weight: .bold))
                    .foregroundStyle(.white))
                .shadow(color: .black.opacity(0.18), radius: 3, y: 1)

            VStack(alignment: .leading, spacing: 1) {
                Text("HDZero Converter")
                    .font(.system(size: 15, weight: .semibold, design: .rounded))
                Text("Make FPV recordings play on every device")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }
            Spacer()
            portableBadge
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 11)
    }

    private var portableBadge: some View {
        HStack(spacing: 5) {
            Circle()
                .fill(model.usingBundledFFmpeg ? Color.green : Color.orange)
                .frame(width: 6, height: 6)
            Text(model.usingBundledFFmpeg ? "ffmpeg embedded" : "system ffmpeg")
                .font(.system(size: 10.5, weight: .medium))
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 5)
        .background(Capsule().fill(Color.secondary.opacity(0.10)))
        .help(model.usingBundledFFmpeg
              ? "Using the ffmpeg bundled inside this app — fully portable, no install needed."
              : "Using ffmpeg found on this Mac. Rebuild with build_app.sh to embed it.")
    }

    // MARK: Left pane — source + action

    private var leftPane: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("SOURCE")
                .font(.system(size: 10.5, weight: .semibold))
                .foregroundStyle(.secondary)
                .kerning(0.6)
                .padding(.bottom, 9)

            dropZone

            VStack(spacing: 7) {
                fileRow(icon: "doc", title: "Input",
                        name: model.inputURL?.lastPathComponent,
                        button: "Choose…", action: chooseInput, enabled: true)
                fileRow(icon: "square.and.arrow.down", title: "Output",
                        name: model.outputURL?.lastPathComponent,
                        button: "Save As…", action: chooseOutput, enabled: model.inputURL != nil)
            }
            .padding(.top, 12)

            Spacer(minLength: 16)

            // Action + progress
            VStack(alignment: .leading, spacing: 9) {
                HStack(spacing: 6) {
                    Text(model.statusMessage)
                        .font(.system(size: 12, weight: .medium))
                    if model.isRunning {
                        Text("\(Int(model.progress * 100))%")
                            .font(.system(size: 12, design: .monospaced))
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    if model.isRunning {
                        Text(model.etaText)
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(.secondary)
                    }
                }
                if !model.isRunning && !model.lastResultSummary.isEmpty {
                    Text(model.lastResultSummary)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
                ProgressView(value: model.progress)
                    .progressViewStyle(.linear)

                if model.isRunning {
                    Button(role: .destructive) { model.cancel() } label: {
                        Label("Cancel", systemImage: "stop.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .controlSize(.large)
                    .keyboardShortcut(".", modifiers: .command)
                } else {
                    Button { model.start() } label: {
                        Label("Convert", systemImage: "wand.and.stars")
                            .frame(maxWidth: .infinity)
                    }
                    .controlSize(.large)
                    .buttonStyle(.borderedProminent)
                    .keyboardShortcut(.return, modifiers: .command)
                    .disabled(model.inputURL == nil)
                }

                if model.statusMessage == "Done ✓" {
                    Button { model.revealOutput() } label: {
                        Label("Reveal in Finder", systemImage: "folder")
                            .frame(maxWidth: .infinity)
                    }
                    .controlSize(.small)
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private func fileRow(icon: String, title: String, name: String?,
                         button: String, action: @escaping () -> Void, enabled: Bool) -> some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
                .frame(width: 16)
            VStack(alignment: .leading, spacing: 1) {
                Text(title)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(.secondary)
                Text(name ?? "—")
                    .font(.system(size: 11.5, design: .monospaced))
                    .lineLimit(1).truncationMode(.middle)
            }
            Spacer(minLength: 4)
            Button(button, action: action)
                .controlSize(.small)
                .disabled(!enabled)
        }
        .padding(9)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color.primary.opacity(0.04)))
    }

    // MARK: Right pane — settings

    private var settingsPane: some View {
        Form {
            Section("Video") {
                Row("Fix color range", info: "THE key fix for HDZero. Source is full-range yuvj420p which Apple decoders mis-read — QuickTime goes black, iPhone goes washed-out white. This converts to standard limited-range yuv420p with BT.709 tags. Leave ON.") {
                    Toggle("", isOn: $model.fixColorRange).labelsHidden()
                }
                Row("Frame rate", info: "HDZero records an odd ~90fps with a variable timebase that some players choke on. 60 fps is the safest universal choice; “Keep original” preserves smoothness but may not play everywhere.") {
                    picker($model.fps, FPSOption.allCases) { $0.rawValue }
                }
                Row("Resolution", info: "Keep the native size or downscale to save space. Width auto-adjusts to preserve aspect ratio. Upscaling won’t add real detail.") {
                    picker($model.resolution, ResolutionOption.allCases) { $0.rawValue }
                }
                Row("Encoder", info: "x264 (software) = best quality and most reliable color handling — recommended. VideoToolbox (hardware) = much faster via the Mac’s media engine, but larger files and uses a bitrate target instead of CRF.") {
                    picker($model.encoder, EncoderOption.allCases) { $0.rawValue }
                }
                if model.encoder == .x264 {
                    Row("Quality", info: "CRF — Constant Rate Factor. Lower = better quality, bigger file. 18 ≈ visually lossless, 20–23 is a great balance, 28+ gets soft. Default 20.") {
                        HStack(spacing: 8) {
                            Slider(value: $model.crf, in: 14...30, step: 1)
                                .frame(width: controlWidth - 34)
                            Text("\(Int(model.crf))")
                                .font(.system(size: 12, design: .monospaced))
                                .foregroundStyle(.secondary)
                                .frame(width: 22, alignment: .trailing)
                        }
                    }
                    Row("Encoding speed", info: "How hard x264 works. Slower presets pack a bit more quality into the same size but take longer. “medium” is the sweet spot.") {
                        picker($model.preset, model.presets, id: \.self) { $0 }
                    }
                } else {
                    Row("Bitrate", info: "Target average bitrate for the hardware encoder. Higher = better quality, bigger file. 15–25 Mbps is plenty for 720p FPV footage.") {
                        HStack(spacing: 8) {
                            Slider(value: $model.bitrateMbps, in: 5...50, step: 1)
                                .frame(width: controlWidth - 52)
                            Text("\(Int(model.bitrateMbps)) Mbps")
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(.secondary)
                                .frame(width: 56, alignment: .trailing)
                        }
                    }
                }
                Row("H.264 profile", info: "Feature set of the stream. “high” is best and supported by virtually all modern devices. Use main/baseline only for very old hardware.") {
                    picker($model.profile, ProfileOption.allCases) { $0.rawValue.capitalized }
                }
                Row("Level", info: "Caps resolution/framerate/bitrate so constrained decoders accept the file. The source’s Level 5.1 is what chokes some players; 4.2 covers 1080p60 and is widely safe.") {
                    picker($model.level, LevelOption.allCases) { $0.rawValue }
                }
            }

            Section("Audio & Container") {
                Row("Audio", info: "Re-encode AAC = safest, standard stereo AAC. Copy = fastest, keeps original audio untouched. Remove = strip audio entirely.") {
                    picker($model.audio, AudioOption.allCases) { $0.rawValue }
                }
                if model.audio == .aac {
                    Row("Audio bitrate", info: "Quality of the re-encoded AAC track. 192 kbps is transparent for most content.") {
                        picker($model.audioBitrate, model.audioBitrates, id: \.self) { "\($0) kbps" }
                    }
                }
                Row("Fast start", info: "Moves the file index (moov atom) to the front so playback starts before the file fully downloads — important for streaming, AirDrop previews and web. Leave ON.") {
                    Toggle("", isOn: $model.faststart).labelsHidden()
                }
            }
        }
        .formStyle(.grouped)
        .scrollContentBackground(.hidden)
    }

    // MARK: Drop zone

    private var dropZone: some View {
        RoundedRectangle(cornerRadius: 11, style: .continuous)
            .strokeBorder(style: StrokeStyle(lineWidth: 1.4, dash: [5]))
            .foregroundStyle(dropTargeted ? Color.accentColor : Color.secondary.opacity(0.35))
            .background(RoundedRectangle(cornerRadius: 11)
                .fill(dropTargeted ? Color.accentColor.opacity(0.08) : Color.primary.opacity(0.02)))
            .frame(height: 118)
            .overlay(
                VStack(spacing: 8) {
                    Image(systemName: model.inputURL == nil ? "arrow.down.doc" : "checkmark.circle.fill")
                        .font(.system(size: 26))
                        .foregroundStyle(model.inputURL == nil ? Color.secondary : Color.green)
                    Text(model.inputURL?.lastPathComponent ?? "Drag a video here\nor click to choose")
                        .font(.system(size: 12))
                        .multilineTextAlignment(.center)
                        .foregroundStyle(model.inputURL == nil ? .secondary : .primary)
                        .lineLimit(2).truncationMode(.middle)
                }.padding(.horizontal, 14)
            )
            .contentShape(Rectangle())
            .onTapGesture { chooseInput() }
            .onDrop(of: [.fileURL], isTargeted: $dropTargeted) { handleDrop($0) }
    }

    // MARK: Picker helpers

    @ViewBuilder
    private func picker<T: Hashable & Identifiable>(
        _ sel: Binding<T>, _ items: [T], label: @escaping (T) -> String
    ) -> some View {
        Picker("", selection: sel) {
            ForEach(items) { Text(label($0)).tag($0) }
        }
        .labelsHidden()
        .frame(width: controlWidth)
    }

    @ViewBuilder
    private func picker<T: Hashable>(
        _ sel: Binding<T>, _ items: [T], id: KeyPath<T, T>, label: @escaping (T) -> String
    ) -> some View {
        Picker("", selection: sel) {
            ForEach(items, id: id) { Text(label($0)).tag($0) }
        }
        .labelsHidden()
        .frame(width: controlWidth)
    }

    // MARK: File actions

    private func chooseInput() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.movie, .mpeg4Movie, .quickTimeMovie, .video]
        if panel.runModal() == .OK, let url = panel.url { model.setInput(url) }
    }

    private func chooseOutput() {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.mpeg4Movie]
        panel.nameFieldStringValue = model.outputURL?.lastPathComponent ?? "output_compatible.mp4"
        if let dir = model.outputURL?.deletingLastPathComponent() { panel.directoryURL = dir }
        if panel.runModal() == .OK, let url = panel.url { model.outputURL = url }
    }

    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        guard let provider = providers.first else { return false }
        _ = provider.loadObject(ofClass: URL.self) { url, _ in
            guard let url else { return }
            DispatchQueue.main.async { model.setInput(url) }
        }
        return true
    }
}

// MARK: - Row with info popover

struct Row<Content: View>: View {
    let title: String
    let info: String
    @ViewBuilder var content: () -> Content

    init(_ title: String, info: String, @ViewBuilder content: @escaping () -> Content) {
        self.title = title
        self.info = info
        self.content = content
    }

    var body: some View {
        LabeledContent {
            HStack(spacing: 7) {
                content()
                InfoButton(text: info)
            }
        } label: {
            Text(title).font(.system(size: 12.5))
        }
    }
}

struct InfoButton: View {
    let text: String
    @State private var show = false

    var body: some View {
        Button { show.toggle() } label: {
            Image(systemName: "info.circle")
                .font(.system(size: 12))
                .foregroundStyle(.tertiary)
        }
        .buttonStyle(.plain)
        .help(text)
        .popover(isPresented: $show, arrowEdge: .trailing) {
            Text(text)
                .font(.system(size: 12))
                .frame(width: 260, alignment: .leading)
                .fixedSize(horizontal: false, vertical: true)
                .padding(13)
        }
    }
}
