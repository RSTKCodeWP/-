import SwiftUI
import UniformTypeIdentifiers

struct VTXView: View {
    @EnvironmentObject var app: AppState
    @EnvironmentObject var c: DeviceController

    @State private var useLocal = false

    var body: some View {
        TwoColumnPage {
            // LEFT — firmware configuration
            Panel(title: "Firmware", systemImage: "shippingbox") {
                Picker("", selection: $useLocal) {
                    Text("Online").tag(false)
                    Text("Local file").tag(true)
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .onChange(of: useLocal) { _ in c.source = .none }

                if useLocal { localPicker } else { onlinePicker }
            }
        } right: {
            // RIGHT — action + status
            Panel(title: "Flash", systemImage: "bolt.fill") {
                Text("Clip a CH341A to the VTX flash chip with the VTX powered, then flash. macOS will ask for your admin password once.")
                    .font(.caption).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)

                DetectRow(c: c)

                VStack(spacing: 8) {
                    Button { Task { await flash() } } label: {
                        Label("Flash VTX", systemImage: "bolt.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .disabled(!canFlash || c.phase.isBusy)

                    Button { Task { await backup() } } label: {
                        Label("Backup current firmware", systemImage: "square.and.arrow.down")
                            .frame(maxWidth: .infinity)
                    }
                    .controlSize(.large)
                    .disabled(c.phase.isBusy)

                    Button { Task { await verify() } } label: {
                        Label("Verify against firmware", systemImage: "checkmark.shield")
                            .frame(maxWidth: .infinity)
                    }
                    .controlSize(.large)
                    .disabled(!canFlash || c.phase.isBusy)
                }
                .padding(.vertical, 2)

                Divider()
                StatusBarView(controller: c)
            }
        }
    }

    // MARK: Source pickers

    private var onlinePicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            Field(label: "Target") {
                Picker("", selection: Binding(
                    get: { c.vtxTarget },
                    set: { c.vtxTarget = $0; c.selectedVersion = nil; updateSource() }
                )) {
                    Text("Select target…").tag(String?.none)
                    ForEach(app.catalog.vtxTargets) { t in
                        Text(t.displayName).tag(String?.some(t.name))
                    }
                }
                .labelsHidden()
            }
            Field(label: "Version") {
                Picker("", selection: Binding(
                    get: { c.selectedVersion },
                    set: { c.selectedVersion = $0; updateSource() }
                )) {
                    Text("Select version…").tag(String?.none)
                    ForEach(versionsForSelectedTarget, id: \.self) { v in
                        Text(v).tag(String?.some(v))
                    }
                }
                .labelsHidden()
                .disabled(c.vtxTarget == nil)
            }
            if app.catalog.state == .loading {
                HStack(spacing: 6) {
                    ProgressView().controlSize(.small)
                    Text("Loading firmware list…").font(.caption).foregroundStyle(.secondary)
                }
            }
        }
    }

    private var localPicker: some View {
        Field(label: "Firmware file (.bin or .zip)") {
            HStack(spacing: 8) {
                Button("Choose…") { chooseLocal() }
                Text(localLabel)
                    .font(.caption).foregroundStyle(.secondary)
                    .lineLimit(1).truncationMode(.middle)
            }
        }
    }

    // MARK: Derived

    private var selectedTarget: FirmwareCatalog.VTXTarget? {
        app.catalog.vtxTargets.first { $0.name == c.vtxTarget }
    }
    private var versionsForSelectedTarget: [String] {
        (selectedTarget?.versions.map(\.version)) ?? []
    }
    private var localLabel: String {
        if case .local(let u) = c.source { return u.lastPathComponent }
        return "No file selected"
    }
    private var canFlash: Bool {
        switch c.source { case .online, .local: return true; case .none: return false }
    }

    private func updateSource() {
        guard let t = selectedTarget, let v = c.selectedVersion,
              let asset = t.versions.first(where: { $0.version == v }) else {
            if !useLocal { c.source = .none }
            return
        }
        c.source = .online(version: v, url: asset.url)
    }

    // MARK: Actions

    private func chooseLocal() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [UTType(filenameExtension: "bin") ?? .data, .zip]
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url { c.source = .local(url) }
    }

    private func flash() async {
        let src: URL
        switch c.source {
        case .local(let u): src = u
        case .online(_, let url):
            c.phase = .downloading
            c.appendLog("Downloading \(url.lastPathComponent)…\n")
            do { src = try await Downloader.download(url) }
            catch { c.fail("Download failed: \(error.localizedDescription)"); return }
        case .none: return
        }
        await FlashromService.flash(source: src, flashrom: app.flashromPath, controller: c)
    }

    private func backup() async {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "hdzero_vtx_backup.bin"
        panel.allowedContentTypes = [UTType(filenameExtension: "bin") ?? .data]
        guard panel.runModal() == .OK, let dest = panel.url else { return }
        await FlashromService.backup(to: dest, flashrom: app.flashromPath, controller: c)
    }

    private func verify() async {
        let src: URL
        switch c.source {
        case .local(let u): src = u
        case .online(_, let url):
            c.phase = .downloading
            c.appendLog("Downloading \(url.lastPathComponent)…\n")
            do { src = try await Downloader.download(url) }
            catch { c.fail("Download failed: \(error.localizedDescription)"); return }
        case .none: return
        }
        await FlashromService.verify(source: src, flashrom: app.flashromPath, controller: c)
    }
}
