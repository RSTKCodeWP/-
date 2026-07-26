import SwiftUI

struct ContentView: View {
    @StateObject private var app = AppState()

    var body: some View {
        VStack(spacing: 0) {
            header

            TabView(selection: $app.selectedTab) {
                VTXView().environmentObject(app).environmentObject(app.vtx)
                    .tabItem { Label("VTX", systemImage: "antenna.radiowaves.left.and.right") }
                    .tag(DeviceKind.vtx)

                MonitorView().environmentObject(app).environmentObject(app.monitor)
                    .tabItem { Label("Monitor", systemImage: "tv") }
                    .tag(DeviceKind.monitor)

                EventVRXView().environmentObject(app).environmentObject(app.eventVRX)
                    .tabItem { Label("Event VRX", systemImage: "dot.radiowaves.up.forward") }
                    .tag(DeviceKind.eventVRX)

                RadioView().environmentObject(app).environmentObject(app.radio)
                    .tabItem { Label("Radio", systemImage: "gamecontroller") }
                    .tag(DeviceKind.radio)

                GoggleView().environmentObject(app).environmentObject(app.goggle2)
                    .tabItem { Label("Goggle 2", systemImage: "eyeglasses") }
                    .tag(DeviceKind.goggle2)
            }
            .padding(.horizontal, 12)
            .disabled(app.anyBusy)   // lock tab switching during an operation
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .task { await app.loadCatalog() }
    }

    private var header: some View {
        HStack(spacing: 10) {
            Image(systemName: "bolt.horizontal.circle.fill")
                .font(.system(size: 22))
                .foregroundStyle(.tint)
            VStack(alignment: .leading, spacing: 1) {
                Text("HDZero Programmer").font(.headline)
                Text("Native macOS · CH341A / serial")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            CatalogStatusBadge().environmentObject(app)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.bar)
    }
}

private struct CatalogStatusBadge: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        Group {
            switch app.catalog.state {
            case .loading:
                HStack(spacing: 6) {
                    ProgressView().controlSize(.small)
                    Text("Loading firmware list…").font(.caption)
                }
            case .ready:
                Label("Firmware list ready", systemImage: "checkmark.circle.fill")
                    .font(.caption).foregroundStyle(.green)
            case .failed(let e):
                Label("Offline: \(e)", systemImage: "wifi.slash")
                    .font(.caption).foregroundStyle(.orange)
            case .idle:
                EmptyView()
            }
        }
    }
}
