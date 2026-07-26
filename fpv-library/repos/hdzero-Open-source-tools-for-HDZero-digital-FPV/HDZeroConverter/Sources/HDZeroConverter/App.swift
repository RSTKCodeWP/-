import SwiftUI

@main
struct HDZeroConverterApp: App {
    @StateObject private var model = ConversionModel()

    var body: some Scene {
        WindowGroup("HDZero Converter") {
            ContentView()
                .environmentObject(model)
                .frame(minWidth: 760, idealWidth: 820, minHeight: 540, idealHeight: 600)
        }
        .windowResizability(.contentMinSize)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
    }
}
