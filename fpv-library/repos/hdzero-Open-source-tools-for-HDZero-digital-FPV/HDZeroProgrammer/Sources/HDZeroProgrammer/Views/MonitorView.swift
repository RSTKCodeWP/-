import SwiftUI

struct MonitorView: View {
    @EnvironmentObject var app: AppState
    @EnvironmentObject var c: DeviceController
    @StateObject private var settings = MonitorSettings()

    var body: some View {
        TwoColumnPage {
            // LEFT — firmware flash
            Panel(title: "Firmware", systemImage: "shippingbox") {
                OnlineLocalPicker(c: c).environmentObject(app)
                DetectRow(c: c)
                Button { Task { await flash() } } label: {
                    Label("Flash Monitor", systemImage: "bolt.fill").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent).controlSize(.large)
                .disabled(!canFlash || c.phase.isBusy)
                Divider()
                StatusBarView(controller: c)
            }
        } right: {
            // RIGHT — live display settings (I2C)
            Panel(title: "Display settings", systemImage: "slider.horizontal.3") {
                HStack {
                    Button(settings.connected ? "Re-read" : "Connect") {
                        Task { await settings.connectAndRead() }
                    }
                    .controlSize(.small)
                    Text(settings.statusMessage).font(.caption).foregroundStyle(.secondary)
                        .lineLimit(1)
                }

                Group {
                    slider("Brightness", $settings.brightness, 0...254) { settings.write(.brightness, $0) }
                    slider("Contrast", $settings.contrast, 0...254) { settings.write(.contrast, $0) }
                    slider("Saturation", $settings.saturation, 0...254) { settings.write(.saturation, $0) }
                    slider("Backlight", $settings.backlight, 1...100) { settings.write(.backlight, $0) }
                    slider("Cell count", $settings.cellCount, 1...6) { settings.write(.cellCount, $0) }
                    slider("Warn cell (×0.1V)", $settings.warningCellV, 28...42) { settings.write(.warningCellV, $0) }
                    Toggle("Enable OSD", isOn: $settings.osd)
                        .font(.caption)
                        .onChange(of: settings.osd) { settings.write(.osd, $0 ? 1 : 0) }
                }
                .disabled(!settings.connected)
            }
        }
    }

    private func slider(_ label: String, _ value: Binding<Double>, _ range: ClosedRange<Double>,
                        write: @escaping (UInt8) -> Void) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(label).font(.caption).foregroundStyle(.secondary)
                Spacer()
                Text("\(Int(value.wrappedValue))").font(.caption.monospacedDigit())
            }
            Slider(value: value, in: range) { editing in
                if !editing { write(UInt8(value.wrappedValue)) }
            }
            .controlSize(.small)
        }
    }

    private var canFlash: Bool {
        switch c.source { case .online, .local: return true; case .none: return false }
    }
    private func flash() async {
        guard let src = await resolveSource(c) else { return }
        await CH341Flasher.flashMonitor(source: src, controller: c)
    }
}
