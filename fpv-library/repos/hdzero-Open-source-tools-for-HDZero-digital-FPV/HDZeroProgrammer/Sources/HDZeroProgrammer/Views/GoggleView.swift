import SwiftUI

/// HDZero Goggle 2 — flashed via CH341A SPI through the goggle's firmware socket
/// + the HDZero Programmer cable. Shipped **Read/Detect-first**: we identify the
/// flash chip safely now; the write is intentionally deferred until the chip and
/// the goggle2 firmware image layout are confirmed (a blind write can brick it).
struct GoggleView: View {
    @EnvironmentObject var app: AppState
    @EnvironmentObject var c: DeviceController

    var body: some View {
        TwoColumnPage {
            // LEFT — read/detect + firmware selection
            Panel(title: "Read / Detect", systemImage: "magnifyingglass") {
                Text("Connect the HDZero Programmer cable to the Goggle 2 firmware socket, then read the flash chip. This is safe — it only reads.")
                    .font(.caption).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                DetectRow(c: c)

                Divider()

                Text("Firmware (for the upcoming write)")
                    .font(.caption).foregroundStyle(.secondary)
                OnlineLocalPicker(c: c).environmentObject(app)
            }
        } right: {
            // RIGHT — write (deferred) + status
            Panel(title: "Flash", systemImage: "bolt.fill") {
                Button { } label: {
                    Label("Flash Goggle 2 — pending chip confirmation", systemImage: "lock.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent).controlSize(.large)
                .disabled(true)

                Label {
                    Text("Writing is disabled until **Read / Detect** identifies the chip and the Goggle 2 firmware format is confirmed. A blind write can brick the goggle.")
                        .font(.caption).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                } icon: {
                    Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
                }

                Divider()
                StatusBarView(controller: c)
            }
        }
    }
}
