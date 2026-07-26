import SwiftUI

struct RadioView: View {
    @EnvironmentObject var app: AppState
    @EnvironmentObject var c: DeviceController

    var body: some View {
        TwoColumnPage {
            Panel(title: "Firmware", systemImage: "shippingbox") {
                OnlineLocalPicker(c: c).environmentObject(app)
                Button { Task { await flash() } } label: {
                    Label("Update Radio", systemImage: "bolt.fill").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent).controlSize(.large)
                .disabled(!canFlash || c.phase.isBusy)
            }
        } right: {
            Panel(title: "Device", systemImage: "info.circle") {
                Text("Updates in three stages over USB-serial: ELRS TX (ESP32), ELRS backpack (ESP32-C3), then the STM32 via XMODEM. Keep the radio connected throughout.")
                    .font(.caption).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                DetectRow(c: c)
                Divider()
                StatusBarView(controller: c)
            }
        }
    }

    private var canFlash: Bool {
        switch c.source { case .online, .local: return true; case .none: return false }
    }
    private func flash() async {
        guard let src = await resolveSource(c) else { return }
        await RadioFlasher.flash(source: src, controller: c)
    }
}

/// Shared two-column placeholder (kept for any not-yet-wired device tab).
struct DevicePlaceholder: View {
    let title: String
    let symbol: String
    let summary: String
    @ObservedObject var controller: DeviceController

    var body: some View {
        TwoColumnPage {
            Panel(title: title, systemImage: symbol) {
                Text(summary).font(.callout).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        } right: {
            Panel(title: "Status", systemImage: "info.circle") {
                StatusBarView(controller: controller)
            }
        }
    }
}
