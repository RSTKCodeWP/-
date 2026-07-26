import SwiftUI

struct EventVRXView: View {
    @EnvironmentObject var app: AppState
    @EnvironmentObject var c: DeviceController

    var body: some View {
        TwoColumnPage {
            Panel(title: "Firmware", systemImage: "shippingbox") {
                OnlineLocalPicker(c: c).environmentObject(app)
                Button { Task { await flash() } } label: {
                    Label("Flash Event VRX", systemImage: "bolt.fill").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent).controlSize(.large)
                .disabled(!canFlash || c.phase.isBusy)
            }
        } right: {
            Panel(title: "Device", systemImage: "info.circle") {
                Text("Two flash chips (5680 + FPGA) are erased then written via the native CH341 driver. The full erase can take over a minute — don't unplug.")
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
        await CH341Flasher.flashEventVRX(source: src, controller: c)
    }
}
