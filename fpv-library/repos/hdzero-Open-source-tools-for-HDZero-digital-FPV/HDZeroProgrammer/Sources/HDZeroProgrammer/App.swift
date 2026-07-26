import SwiftUI

@main
struct HDZeroProgrammerApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
                .frame(minWidth: 720, idealWidth: 760, minHeight: 480, idealHeight: 520)
        }
        .windowResizability(.contentSize)
        .commands {
            // Replace the default "New Window" — this is a single-window utility.
            CommandGroup(replacing: .newItem) {}
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}
