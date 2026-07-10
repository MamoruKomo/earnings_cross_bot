import SwiftUI

@main struct EarningsCrossManagerApp: App {
    @StateObject private var model = AppModel()
    var body: some Scene {
        WindowGroup { RootView().environmentObject(model) }
            .defaultSize(width: 1180, height: 760)
            .commands { CommandGroup(after: .newItem) { Button("データを再読み込み") { model.reload() }.keyboardShortcut("r", modifiers: .command) } }
    }
}
