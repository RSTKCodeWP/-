import SwiftUI

/// Compact status + progress + collapsible log, designed to sit inside a Panel
/// (no background of its own). Driven by a DeviceController.
struct StatusBarView: View {
    @ObservedObject var controller: DeviceController
    @State private var showLog = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                statusIcon
                Text(statusText)
                    .font(.callout.weight(.medium))
                    .foregroundStyle(statusColor)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
            }

            if controller.phase.isBusy {
                if case .flashing = controller.phase, controller.progress > 0 {
                    ProgressView(value: controller.progress).controlSize(.small)
                } else {
                    ProgressView().progressViewStyle(.linear).controlSize(.small)
                }
            }

            if !controller.log.isEmpty {
                Button(showLog ? "Hide log" : "Show log") { showLog.toggle() }
                    .buttonStyle(.link).font(.caption)
            }

            if showLog {
                ScrollViewReader { proxy in
                    ScrollView {
                        Text(controller.log)
                            .font(.system(.caption2, design: .monospaced))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .textSelection(.enabled)
                            .id("logtail")
                    }
                    .frame(maxHeight: 180)
                    .background(Color(nsColor: .textBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .onChange(of: controller.log) { _ in
                        withAnimation { proxy.scrollTo("logtail", anchor: .bottom) }
                    }
                }
            }
        }
    }

    @ViewBuilder private var statusIcon: some View {
        switch controller.phase {
        case .idle:   Image(systemName: "circle.dashed").foregroundStyle(.secondary)
        case .done:   Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
        case .failed: Image(systemName: "xmark.octagon.fill").foregroundStyle(.red)
        default:      Image(systemName: "bolt.fill").foregroundStyle(.yellow)
        }
    }

    private var statusText: String {
        switch controller.phase {
        case .idle:          return "Idle"
        case .connecting:    return "Connecting to device…"
        case .downloading:   return "Downloading firmware…"
        case .preparing:     return "Preparing firmware…"
        case .erasing:       return "Erasing flash…"
        case .flashing:      return "Writing firmware…"
        case .verifying:     return "Verifying…"
        case .done(let s):   return s
        case .failed(let s): return s
        }
    }

    private var statusColor: Color {
        switch controller.phase {
        case .done:   return .green
        case .failed: return .red
        default:      return .primary
        }
    }
}
