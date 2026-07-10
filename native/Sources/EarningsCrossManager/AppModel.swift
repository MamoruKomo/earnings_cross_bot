import Foundation
import SwiftUI

@MainActor final class AppModel: ObservableObject {
    @Published var data: DashboardData?
    @Published var selectedSection: AppSection? = .overview
    @Published var selectedDate = Date()
    @Published var isRunning = false
    @Published var statusMessage = "データを読み込んでいます"
    @Published var commandLog = ""
    @Published var lastError: String?
    let repositoryURL: URL

    init() { repositoryURL = Self.findRepositoryURL(); reload() }

    func reload() {
        do {
            let raw = try Data(contentsOf: repositoryURL.appendingPathComponent("docs/dashboard/data/dashboard.json"))
            data = try JSONDecoder().decode(DashboardData.self, from: raw)
            statusMessage = "最新データを表示中"; lastError = nil
        } catch { lastError = "ダッシュボードデータを読み込めません: \(error.localizedDescription)"; statusMessage = "読み込みエラー" }
    }

    func runMorning() { run(module: "src.main_morning", label: "朝の候補生成", includesDate: true) }
    func runEvaluation() { run(module: "src.main_evaluate", label: "結果評価", includesDate: true) }
    func runWeeklyReview() { run(module: "src.main_weekly_review", label: "週次レビュー", includesDate: true) }
    func rebuildDashboard() { run(module: "src.main_dashboard", label: "データ更新", includesDate: false) }

    private func run(module: String, label: String, includesDate: Bool) {
        guard !isRunning else { return }
        isRunning = true; lastError = nil; statusMessage = "\(label)を実行中"; commandLog = "$ python3 -m \(module)"
        let repo = repositoryURL; let dateValue = Self.isoDate.string(from: selectedDate)
        Task.detached {
            do {
                var arguments = ["-m", module]; if includesDate { arguments += ["--date", dateValue] }
                let python = Self.pythonExecutable(in: repo)
                let first = try Self.execute(python, arguments: arguments, in: repo)
                let dashboard = try Self.execute(python, arguments: ["-m", "src.main_dashboard"], in: repo)
                await MainActor.run {
                    self.commandLog = [first, dashboard].filter { !$0.isEmpty }.joined(separator: "\n")
                    self.isRunning = false; self.statusMessage = "\(label)が完了しました"; self.reload()
                }
            } catch {
                await MainActor.run { self.isRunning = false; self.statusMessage = "\(label)に失敗しました"; self.lastError = error.localizedDescription; self.commandLog += "\n\(error.localizedDescription)" }
            }
        }
    }

    nonisolated private static func execute(_ executable: String, arguments: [String], in directory: URL) throws -> String {
        let process = Process(); let pipe = Pipe()
        process.executableURL = URL(fileURLWithPath: executable); process.arguments = arguments
        process.currentDirectoryURL = directory; process.standardOutput = pipe; process.standardError = pipe
        try process.run(); process.waitUntilExit()
        let output = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        guard process.terminationStatus == 0 else { throw RunnerError.commandFailed(output.trimmingCharacters(in: .whitespacesAndNewlines)) }
        return output.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func findRepositoryURL() -> URL {
        if let configured = ProcessInfo.processInfo.environment["EARNINGS_CROSS_REPO"] { return URL(fileURLWithPath: configured) }
        var candidate = Bundle.main.bundleURL; for _ in 0..<2 { candidate.deleteLastPathComponent() }
        if FileManager.default.fileExists(atPath: candidate.appendingPathComponent("src/main_morning.py").path) { return candidate }
        return URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    }

    nonisolated private static func pythonExecutable(in repository: URL) -> String {
        let virtualEnvironment = repository.appendingPathComponent(".venv/bin/python3").path
        return FileManager.default.isExecutableFile(atPath: virtualEnvironment) ? virtualEnvironment : "/usr/bin/python3"
    }

    static let isoDate: DateFormatter = { let f = DateFormatter(); f.calendar = Calendar(identifier: .gregorian); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd"; return f }()
}

enum RunnerError: LocalizedError {
    case commandFailed(String)
    var errorDescription: String? { switch self { case .commandFailed(let output): output.isEmpty ? "処理が失敗しました" : output } }
}
