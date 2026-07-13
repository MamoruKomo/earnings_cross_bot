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

    func runMorning() { runGitHubJob(job: "morning", label: "今日の候補生成") }
    func runEvaluation() { runGitHubJob(job: "evaluate", label: "結果評価") }
    func runWeeklyReview() { runGitHubJob(job: "weekly", label: "週次レビュー") }
    func runLearning() { runGitHubJob(job: "learn", label: "自己学習") }
    func runSlackTest() { runGitHubJob(job: "slack-test", label: "Slack接続テスト") }
    func syncLatest() {
        guard !isRunning else { return }
        isRunning = true; lastError = nil; statusMessage = "最新データを同期中"
        commandLog = "$ git pull --rebase origin main"
        let repo = repositoryURL
        Task.detached {
            do {
                let output = try Self.pullLatest(in: repo)
                await MainActor.run {
                    self.commandLog = output; self.isRunning = false; self.statusMessage = "最新データへ更新しました"; self.reload()
                }
            } catch {
                await MainActor.run {
                    self.isRunning = false; self.statusMessage = "データ同期に失敗しました"
                    self.lastError = error.localizedDescription; self.commandLog += "\n\(error.localizedDescription)"
                }
            }
        }
    }

    private func runGitHubJob(job: String, label: String) {
        guard !isRunning else { return }
        isRunning = true; lastError = nil; statusMessage = "\(label)を実行中"
        commandLog = "$ gh workflow run \"Earnings Cross Bot\" -f job=\(job)"
        let repo = repositoryURL
        Task.detached {
            do {
                let gh = try Self.githubExecutable()
                let dispatch = try Self.execute(gh, arguments: ["workflow", "run", "Earnings Cross Bot", "-R", "MamoruKomo/earnings_cross_bot", "-f", "job=\(job)"], in: repo)
                guard let url = dispatch.split(separator: "\n").last, let runID = url.split(separator: "/").last else {
                    throw RunnerError.commandFailed("GitHub Actionsの実行IDを取得できませんでした。\n\(dispatch)")
                }
                let watch = try Self.execute(gh, arguments: ["run", "watch", String(runID), "-R", "MamoruKomo/earnings_cross_bot", "--exit-status"], in: repo)
                let sync = try Self.pullLatest(in: repo)
                await MainActor.run {
                    self.commandLog = "\(dispatch)\n\(watch)\n\(sync)"
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

    nonisolated private static func githubExecutable() throws -> String {
        let candidates = ["/opt/homebrew/bin/gh", "/usr/local/bin/gh"]
        if let executable = candidates.first(where: { FileManager.default.isExecutableFile(atPath: $0) }) { return executable }
        throw RunnerError.commandFailed("GitHub CLI（gh）が見つかりません。Homebrewで gh をインストールしてください。")
    }

    nonisolated private static func pullLatest(in repository: URL) throws -> String {
        try execute("/usr/bin/git", arguments: ["pull", "--rebase", "origin", "main"], in: repository)
    }

    private static func findRepositoryURL() -> URL {
        if let configured = ProcessInfo.processInfo.environment["EARNINGS_CROSS_REPO"] { return URL(fileURLWithPath: configured) }
        var candidate = Bundle.main.bundleURL; for _ in 0..<2 { candidate.deleteLastPathComponent() }
        if FileManager.default.fileExists(atPath: candidate.appendingPathComponent("src/main_morning.py").path) { return candidate }
        return URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    }

}

enum RunnerError: LocalizedError {
    case commandFailed(String)
    var errorDescription: String? { switch self { case .commandFailed(let output): output.isEmpty ? "処理が失敗しました" : output } }
}
