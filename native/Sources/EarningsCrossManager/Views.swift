import Charts
import SwiftUI

struct RootView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        NavigationSplitView {
            VStack(spacing: 0) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("EARNINGS CROSS").font(.caption.bold()).foregroundStyle(.secondary)
                    Text("決算跨ぎ 管理").font(.title2.weight(.semibold))
                }.frame(maxWidth: .infinity, alignment: .leading).padding(18)
                List(AppSection.allCases, selection: $model.selectedSection) { item in Label(item.rawValue, systemImage: item.icon).tag(item) }.listStyle(.sidebar)
                HStack(spacing: 8) {
                    Circle().fill(model.lastError == nil ? Color.green : Color.red).frame(width: 8, height: 8)
                    Text(model.statusMessage).font(.caption).lineLimit(2)
                }.frame(maxWidth: .infinity, alignment: .leading).padding(16)
            }.navigationSplitViewColumnWidth(min: 210, ideal: 235, max: 270)
        } detail: {
            Group {
                switch model.selectedSection ?? .overview {
                case .overview: OverviewView()
                case .history: HistoryView()
                case .stocks: StocksView()
                case .operations: OperationsView()
                }
            }.frame(minWidth: 760, minHeight: 560).background(Color(nsColor: .windowBackgroundColor))
        }
        .toolbar { if model.isRunning { ProgressView().controlSize(.small) }; Button { model.reload() } label: { Image(systemName: "arrow.clockwise") }.help("表示データを再読み込み") }
    }
}

struct OverviewView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        ScrollView {
            if let data = model.data {
                VStack(alignment: .leading, spacing: 22) {
                    PageHeading(title: "運用サマリー", subtitle: "推奨結果と翌営業日の反応をまとめて確認")
                    if data.summary.evaluatedCount < 30 { NoticeView(text: "現在の評価母数は \(data.summary.evaluatedCount) 件です。勝率は参考値として扱い、30件以上たまってから傾向を判断してください。") }
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: 4), spacing: 12) {
                        MetricTile(label: "勝率", value: percent(data.summary.hitRate), detail: "\(data.summary.winCount)勝 / \(data.summary.evaluatedCount)件", color: .green)
                        MetricTile(label: "平均終値反応", value: signedPercent(data.summary.avgNextCloseReturn), detail: "翌営業日終値", color: .blue)
                        MetricTile(label: "プラス着地率", value: percent(data.summary.positiveCloseRate), detail: "終値が決算日超え", color: .mint)
                        MetricTile(label: "未評価", value: "\(data.summary.pendingCount)", detail: "推奨総数 \(data.summary.recommendationCount)", color: .orange)
                    }
                    HStack(alignment: .top, spacing: 14) {
                        Panel(title: "累積リターン", subtitle: "各推奨を同額で連続保有した参考値") {
                            if data.equityCurve.isEmpty { EmptyState(text: "評価データがありません") } else {
                                Chart(data.equityCurve) { point in
                                    AreaMark(x: .value("日付", point.date), y: .value("累積", point.cumulativeReturn)).foregroundStyle(.blue.opacity(0.12))
                                    LineMark(x: .value("日付", point.date), y: .value("累積", point.cumulativeReturn)).foregroundStyle(.blue).lineStyle(.init(lineWidth: 2))
                                    PointMark(x: .value("日付", point.date), y: .value("累積", point.cumulativeReturn)).foregroundStyle(resultColor(point.result))
                                }.chartYScale(domain: .automatic(includesZero: true)).frame(height: 220)
                            }
                        }
                        Panel(title: "判定内訳", subtitle: "設定済みの±3%ルール") {
                            Chart {
                                SectorMark(angle: .value("件数", data.resultDistribution.win), innerRadius: .ratio(0.62)).foregroundStyle(Color.green)
                                SectorMark(angle: .value("件数", data.resultDistribution.neutral), innerRadius: .ratio(0.62)).foregroundStyle(Color.gray.opacity(0.5))
                                SectorMark(angle: .value("件数", data.resultDistribution.lose), innerRadius: .ratio(0.62)).foregroundStyle(Color.red)
                            }.frame(height: 180)
                            HStack { LegendDot(color: .green, text: "勝ち \(data.resultDistribution.win)"); LegendDot(color: .gray, text: "中立 \(data.resultDistribution.neutral)"); LegendDot(color: .red, text: "負け \(data.resultDistribution.lose)") }
                        }.frame(width: 280)
                    }
                    PendingStrip(items: data.pendingRecommendations)
                }.padding(26)
            } else { ContentUnavailableView("データを読み込めません", systemImage: "exclamationmark.triangle", description: Text(model.lastError ?? "不明なエラー")) }
        }
    }
}

struct HistoryView: View {
    @EnvironmentObject private var model: AppModel
    @State private var search = ""
    var filtered: [Outcome] { let rows = model.data?.recentOutcomes ?? []; return search.isEmpty ? rows : rows.filter { $0.code.localizedCaseInsensitiveContains(search) || $0.name.localizedCaseInsensitiveContains(search) } }
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            PageHeading(title: "推奨履歴", subtitle: "スコアと翌営業日の実績を照合")
            Table(filtered) {
                TableColumn("評価日", value: \.evaluationDate).width(90)
                TableColumn("銘柄") { row in StockName(name: row.name, code: row.code) }.width(min: 150, ideal: 210)
                TableColumn("スコア") { row in ScoreBadge(score: row.score) }.width(65)
                TableColumn("判定") { row in ResultBadge(result: row.result) }.width(75)
                TableColumn("翌日始値") { row in Text(signedPercent(row.nextOpenReturn)).monospacedDigit() }.width(85)
                TableColumn("翌日終値") { row in Text(signedPercent(row.nextCloseReturn)).monospacedDigit().foregroundStyle(returnColor(row.nextCloseReturn)) }.width(85)
                TableColumn("最大下落") { row in Text(signedPercent(row.maxDrawdown)).monospacedDigit() }.width(85)
            }.searchable(text: $search, prompt: "銘柄名・コード")
        }.padding(26)
    }
}

struct StocksView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            PageHeading(title: "銘柄別成績", subtitle: "繰り返し推奨された銘柄の傾向")
            Table(model.data?.byCode ?? []) {
                TableColumn("銘柄") { row in StockName(name: row.name, code: row.code) }.width(min: 180, ideal: 250)
                TableColumn("推奨") { row in Text("\(row.recommendationCount)件") }.width(70)
                TableColumn("評価済み") { row in Text("\(row.evaluatedCount)件") }.width(75)
                TableColumn("勝率") { row in Text(percent(row.hitRate)).monospacedDigit() }.width(75)
                TableColumn("平均終値") { row in Text(signedPercent(row.avgNextCloseReturn)).monospacedDigit().foregroundStyle(returnColor(row.avgNextCloseReturn)) }.width(90)
                TableColumn("勝 / 中立 / 負") { row in Text("\(row.win) / \(row.neutral) / \(row.lose)").monospacedDigit() }.width(110)
                TableColumn("最終推奨", value: \.lastRecommendationDate).width(90)
            }
        }.padding(26)
    }
}

struct OperationsView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                PageHeading(title: "運用", subtitle: "日付を指定してPythonパイプラインを実行")
                HStack(alignment: .bottom) {
                    VStack(alignment: .leading, spacing: 7) { Text("対象日").font(.caption.bold()).foregroundStyle(.secondary); DatePicker("対象日", selection: $model.selectedDate, displayedComponents: .date).labelsHidden() }
                    Spacer(); Button { model.rebuildDashboard() } label: { Label("表示を更新", systemImage: "arrow.clockwise") }.disabled(model.isRunning)
                }
                Divider()
                HStack(spacing: 12) {
                    OperationButton(title: "候補を生成", detail: "スコアリングしてSlackへ投稿", icon: "sparkles", tint: .blue, action: model.runMorning)
                    OperationButton(title: "結果を評価", detail: "翌営業日の値動きを判定", icon: "checkmark.seal", tint: .green, action: model.runEvaluation)
                    OperationButton(title: "週次レビュー", detail: "改善案をルール候補へ保存", icon: "calendar.badge.clock", tint: .orange, action: model.runWeeklyReview)
                }.disabled(model.isRunning)
                Panel(title: "実行ログ", subtitle: model.repositoryURL.path) {
                    ScrollView { Text(model.commandLog.isEmpty ? "まだこのアプリから処理を実行していません。" : model.commandLog).font(.system(.caption, design: .monospaced)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading) }.frame(minHeight: 150, maxHeight: 280)
                }
                NoticeView(text: "Slack WebhookやJ-Quantsの認証情報はリポジトリ直下の .env から読み込みます。未設定時はモック/CSVデータで動作し、Slack本文はログにプレビューされます。")
            }.padding(26)
        }
    }
}

struct PageHeading: View { let title, subtitle: String; var body: some View { VStack(alignment: .leading, spacing: 5) { Text(title).font(.largeTitle.bold()); Text(subtitle).foregroundStyle(.secondary) } } }
struct NoticeView: View { let text: String; var body: some View { Label(text, systemImage: "info.circle.fill").font(.callout).foregroundStyle(.secondary).padding(12).frame(maxWidth: .infinity, alignment: .leading).background(Color.blue.opacity(0.08), in: RoundedRectangle(cornerRadius: 6)) } }
struct MetricTile: View { let label, value, detail: String; let color: Color; var body: some View { VStack(alignment: .leading, spacing: 8) { HStack { Text(label).font(.caption.bold()).foregroundStyle(.secondary); Spacer(); Circle().fill(color).frame(width: 7, height: 7) }; Text(value).font(.system(size: 28, weight: .bold, design: .rounded)).monospacedDigit(); Text(detail).font(.caption).foregroundStyle(.secondary) }.padding(15).frame(maxWidth: .infinity, alignment: .leading).panelStyle() } }
struct Panel<Content: View>: View { let title, subtitle: String; @ViewBuilder let content: Content; init(title: String, subtitle: String, @ViewBuilder content: () -> Content) { self.title = title; self.subtitle = subtitle; self.content = content() }; var body: some View { VStack(alignment: .leading, spacing: 14) { VStack(alignment: .leading, spacing: 3) { Text(title).font(.headline); Text(subtitle).font(.caption).foregroundStyle(.secondary) }; content }.padding(16).frame(maxWidth: .infinity, alignment: .leading).panelStyle() } }
struct PendingStrip: View { let items: [PendingRecommendation]; var body: some View { Panel(title: "未評価の推奨", subtitle: "翌営業日の評価待ち") { if items.isEmpty { EmptyState(text: "未評価の推奨はありません") } else { ForEach(items) { item in HStack { StockName(name: item.name, code: "\(item.code)  発表 \(item.eventDate)"); Spacer(); ScoreBadge(score: item.score); Text(item.action).font(.caption.bold()).frame(width: 82) }.padding(.vertical, 5); if item.id != items.last?.id { Divider() } } } } } }
struct OperationButton: View { let title, detail, icon: String; let tint: Color; let action: () -> Void; var body: some View { Button(action: action) { VStack(alignment: .leading, spacing: 12) { Image(systemName: icon).font(.title2).foregroundStyle(tint); Text(title).font(.headline); Text(detail).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.leading) }.padding(16).frame(maxWidth: .infinity, minHeight: 120, alignment: .leading).panelStyle() }.buttonStyle(.plain) } }
struct StockName: View { let name, code: String; var body: some View { VStack(alignment: .leading) { Text(name).fontWeight(.medium); Text(code).font(.caption).foregroundStyle(.secondary) } } }
struct ScoreBadge: View { let score: Int; var body: some View { Text("\(score)").font(.caption.bold()).monospacedDigit().padding(.horizontal, 8).padding(.vertical, 4).background((score >= 80 ? Color.green : Color.blue).opacity(0.12), in: Capsule()).foregroundStyle(score >= 80 ? .green : .blue) } }
struct ResultBadge: View { let result: String; var body: some View { Text(result == "win" ? "勝ち" : result == "lose" ? "負け" : "中立").font(.caption.bold()).padding(.horizontal, 8).padding(.vertical, 4).background(resultColor(result).opacity(0.12), in: Capsule()).foregroundStyle(resultColor(result)) } }
struct LegendDot: View { let color: Color; let text: String; var body: some View { HStack(spacing: 5) { Circle().fill(color).frame(width: 7, height: 7); Text(text).font(.caption) } } }
struct EmptyState: View { let text: String; var body: some View { Text(text).foregroundStyle(.secondary).frame(maxWidth: .infinity, minHeight: 80) } }
extension View { func panelStyle() -> some View { background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 7)).overlay(RoundedRectangle(cornerRadius: 7).stroke(Color.primary.opacity(0.08))) } }
func percent(_ value: Double?) -> String { guard let value else { return "--" }; return value.formatted(.percent.precision(.fractionLength(0))) }
func signedPercent(_ value: Double?) -> String { guard let value else { return "--" }; return value.formatted(.percent.precision(.fractionLength(1)).sign(strategy: .always())) }
func resultColor(_ result: String) -> Color { result == "win" ? .green : result == "lose" ? .red : .gray }
func returnColor(_ value: Double?) -> Color { guard let value else { return .secondary }; return value > 0 ? .green : value < 0 ? .red : .secondary }
