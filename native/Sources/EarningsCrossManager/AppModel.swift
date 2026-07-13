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
    nonisolated private static let snapshotURL = URL(string: "https://raw.githubusercontent.com/MamoruKomo/earnings_cross_bot/main/data/manager_snapshot.json")!

    init() { repositoryURL = Self.findRepositoryURL(); reload() }

    func reload() {
        do {
            let candidates = Self.snapshotLocations(repository: repositoryURL).compactMap { source -> DashboardData? in
                guard FileManager.default.fileExists(atPath: source.path),
                      let raw = try? Data(contentsOf: source),
                      let decoded = try? JSONDecoder().decode(DashboardData.self, from: raw) else { return nil }
                return decoded
            }
            guard let latest = candidates.max(by: { $0.generatedAt < $1.generatedAt }) else {
                throw RunnerError.commandFailed("表示用データがありません。インターネット接続後に同期してください。")
            }
            data = latest
            let overall = latest.marketIntelligence?.health?.overall
            statusMessage = overall == "stale" ? "期限切れデータがあります" : overall == "warning" ? "更新時刻を確認してください" : "最新データを表示中"
            lastError = nil
        } catch { lastError = "ダッシュボードデータを読み込めません: \(error.localizedDescription)"; statusMessage = "読み込みエラー" }
    }

    func runMorning() { runGitHubJob(job: "morning", label: "今日の候補生成") }
    func runEvaluation() { runGitHubJob(job: "evaluate", label: "結果評価") }
    func runWeeklyReview() { runGitHubJob(job: "weekly", label: "週次レビュー") }
    func runLearning() { runGitHubJob(job: "learn", label: "自己学習") }
    func runSlackTest() { runGitHubJob(job: "slack-test", label: "Slack接続テスト") }
    func runMarketBrief() { runGitHubJob(job: "market-brief", label: "朝刊生成") }
    func runDisclosures() { runGitHubJob(job: "tdnet", label: "適時開示更新") }
    func runWatchlist() { runGitHubJob(job: "watchlist-close", label: "ウォッチ更新") }
    func syncLatest() {
        guard !isRunning else { return }
        isRunning = true; lastError = nil; statusMessage = "最新データを同期中"
        commandLog = "$ 最新スナップショットを取得"
        Task {
            do {
                let (raw, response) = try await URLSession.shared.data(from: Self.snapshotURL)
                guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw RunnerError.commandFailed("最新データの取得に失敗しました") }
                try Self.saveCachedSnapshot(raw)
                self.commandLog = "GitHubから最新スナップショットを取得しました"
                self.isRunning = false; self.statusMessage = "最新データへ更新しました"; self.reload()
            } catch {
                self.isRunning = false; self.statusMessage = "データ同期に失敗しました"
                self.lastError = error.localizedDescription; self.commandLog += "\n\(error.localizedDescription)"
            }
        }
    }

    private func runGitHubJob(job: String, label: String) {
        guard !isRunning else { return }
        isRunning = true; lastError = nil; statusMessage = "\(label)を実行中"
        commandLog = "$ gh workflow run \"Earnings Cross Manager Operations\" -f job=\(job)"
        let repo = repositoryURL
        Task.detached {
            do {
                let gh = try Self.githubExecutable()
                let dispatch = try Self.execute(gh, arguments: ["workflow", "run", "Earnings Cross Manager Operations", "-R", "MamoruKomo/earnings_cross_bot", "-f", "job=\(job)"], in: repo)
                guard let url = dispatch.split(separator: "\n").last, let runID = url.split(separator: "/").last else {
                    throw RunnerError.commandFailed("GitHub Actionsの実行IDを取得できませんでした。\n\(dispatch)")
                }
                let watch = try Self.execute(gh, arguments: ["run", "watch", String(runID), "-R", "MamoruKomo/earnings_cross_bot", "--exit-status"], in: repo)
                let raw = try Data(contentsOf: Self.snapshotURL)
                try Self.saveCachedSnapshot(raw)
                await MainActor.run {
                    self.commandLog = "\(dispatch)\n\(watch)\n最新スナップショットを取得しました"
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

    nonisolated private static func saveCachedSnapshot(_ data: Data) throws {
        let destination = try cacheSnapshotURL()
        try FileManager.default.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: destination, options: .atomic)
    }

    nonisolated private static func cacheSnapshotURL() throws -> URL {
        let base = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        return base.appendingPathComponent("EarningsCrossManager/manager_snapshot.json")
    }

    private static func snapshotLocations(repository: URL) -> [URL] {
        var locations: [URL] = []
        if let cached = try? cacheSnapshotURL() { locations.append(cached) }
        locations.append(repository.appendingPathComponent("data/manager_snapshot.json"))
        if let bundled = Bundle.main.url(forResource: "manager_snapshot", withExtension: "json") { locations.append(bundled) }
        return locations
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
