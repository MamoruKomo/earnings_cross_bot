import Charts
import SwiftUI

struct RootView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        NavigationSplitView {
            VStack(spacing: 0) {
                VStack(alignment: .leading, spacing: 3) {
                    Text("EARNINGS CROSS").font(.caption.bold()).foregroundStyle(.secondary)
                    Text("決算跨ぎ 管理").font(.title2.weight(.semibold))
                }.frame(maxWidth: .infinity, alignment: .leading).padding(18)
                List(AppSection.allCases, selection: $model.selectedSection) { item in
                    Label(item.rawValue, systemImage: item.icon).tag(item)
                }.listStyle(.sidebar)
                StatusFooter().padding(16)
            }.navigationSplitViewColumnWidth(min: 190, ideal: 215, max: 240)
        } detail: {
            Group {
                switch model.selectedSection ?? .overview {
                case .overview: TodayView()
                case .history: ReviewView()
                case .analysis: ResearchView()
                case .operations: SettingsView()
                }
            }.frame(minWidth: 820, minHeight: 620)
        }
        .toolbar {
            if model.isRunning { ProgressView().controlSize(.small) }
            Button { model.syncLatest() } label: { Image(systemName: "arrow.triangle.2.circlepath") }.help("最新データを同期")
        }
    }
}

struct TodayView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        ScrollView {
            if let data = model.data {
                VStack(alignment: .leading, spacing: 20) {
                    HStack(alignment: .top) {
                        PageHeading(title: "今日の判断", subtitle: todayDisplay())
                        Spacer()
                        Button { model.runMorning() } label: { Label("候補を再判定", systemImage: "sparkles") }
                            .buttonStyle(.borderedProminent).disabled(model.isRunning)
                    }
                    RunBanner()
                    NotificationBand(status: data.latestNotification)
                    TodayCandidates(items: data.pendingRecommendations)
                    HStack(spacing: 12) {
                        MetricTile(label: "検証済み", value: "\(data.summary.evaluatedCount)件", detail: "学習開始 30件", color: .blue)
                        MetricTile(label: "勝率", value: percent(data.summary.hitRate), detail: "勝ち \(data.summary.winCount) / 負け \(data.summary.loseCount)", color: .green)
                        MetricTile(label: "平均反応", value: signedPercent(data.summary.avgNextCloseReturn), detail: "翌営業日終値", color: .indigo)
                    }
                    if data.summary.evaluatedCount < 30 {
                        NoticeView(icon: "hourglass", text: "まだ検証母数が少ないため、勝率は参考値です。あと \(30 - data.summary.evaluatedCount) 件で重み学習を開始します。")
                    }
                }.padding(26)
            } else { LoadErrorView() }
        }
    }
}

struct TodayCandidates: View {
    let items: [PendingRecommendation]
    private var todayItems: [PendingRecommendation] { items.filter { $0.eventDate == todayISO() } }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack { Text(todayItems.isEmpty ? "本日は見送り" : "跨ぎ候補 \(todayItems.count)銘柄").font(.title2.bold()); Spacer(); Text("最大3銘柄").font(.caption).foregroundStyle(.secondary) }
            if todayItems.isEmpty {
                HStack(spacing: 14) {
                    Image(systemName: "hand.raised.fill").font(.system(size: 30)).foregroundStyle(.orange)
                    VStack(alignment: .leading, spacing: 4) {
                        Text("無理に跨ぐ銘柄はありません").font(.headline)
                        Text("候補生成前、または基準点を満たす銘柄がない状態です。通知状態も確認してください。")
                            .font(.callout).foregroundStyle(.secondary)
                    }
                }.padding(18).frame(maxWidth: .infinity, alignment: .leading).panelStyle()
            } else {
                ForEach(todayItems) { item in CandidateCard(item: item) }
            }
        }
    }
}

struct CandidateCard: View {
    let item: PendingRecommendation
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                StockName(name: item.name, code: item.code)
                Spacer()
                VStack(alignment: .trailing, spacing: 5) {
                    ScoreBadge(score: item.score)
                    Text(actionLabel(item.action)).font(.caption.bold()).foregroundStyle(actionColor(item.action))
                }
            }
            if let thesis = item.thesis, !thesis.isEmpty {
                Label(thesis, systemImage: "lightbulb.fill").font(.callout).fixedSize(horizontal: false, vertical: true)
            }
            HStack(spacing: 18) {
                Fact(icon: "clock", text: item.announcementTime ?? "時刻未取得")
                Fact(icon: "gauge.with.dots.needle.50percent", text: "確信度 \(confidenceLabel(item.confidence))")
            }
            if !item.riskFactors.isEmpty { TagLine(title: "注意", values: item.riskFactors, color: .orange) }
            if !item.missingData.isEmpty { TagLine(title: "未取得", values: item.missingData, color: .gray) }
        }.padding(17).panelStyle()
    }
}

struct ReviewView: View {
    @EnvironmentObject private var model: AppModel
    @State private var search = ""
    var rows: [Outcome] { let all = model.data?.recentOutcomes ?? []; return search.isEmpty ? all : all.filter { $0.code.contains(search) || $0.name.localizedCaseInsensitiveContains(search) } }
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top) {
                PageHeading(title: "検証", subtitle: "推奨が翌営業日にどう動いたか")
                Spacer()
                Button { model.runEvaluation() } label: { Label("結果を更新", systemImage: "checkmark.seal") }.disabled(model.isRunning)
            }
            if let data = model.data {
                HStack(spacing: 12) {
                    MetricTile(label: "勝ち", value: "\(data.summary.winCount)", detail: "+3%以上", color: .green)
                    MetricTile(label: "中立", value: "\(data.summary.neutralCount)", detail: "-3%〜+3%", color: .gray)
                    MetricTile(label: "負け", value: "\(data.summary.loseCount)", detail: "-3%以下", color: .red)
                    MetricTile(label: "平均", value: signedPercent(data.summary.avgNextCloseReturn), detail: "翌日終値", color: .indigo)
                }
            }
            Table(rows) {
                TableColumn("評価日", value: \.evaluationDate).width(90)
                TableColumn("銘柄") { StockName(name: $0.name, code: $0.code) }.width(min: 150, ideal: 210)
                TableColumn("推奨") { Text(actionLabel($0.action)).foregroundStyle(actionColor($0.action)) }.width(80)
                TableColumn("結果") { ResultBadge(result: $0.result) }.width(70)
                TableColumn("翌日始値") { Text(signedPercent($0.nextOpenReturn)).monospacedDigit() }.width(85)
                TableColumn("翌日終値") { Text(signedPercent($0.nextCloseReturn)).monospacedDigit().foregroundStyle(returnColor($0.nextCloseReturn)) }.width(85)
                TableColumn("最大下落") { Text(signedPercent($0.maxDrawdown)).monospacedDigit() }.width(85)
            }.searchable(text: $search, prompt: "銘柄名・コード")
        }.padding(26)
    }
}

struct ResearchView: View {
    @EnvironmentObject private var model: AppModel
    @State private var search = ""
    var rows: [StockSnapshot] { let all = model.data?.stockSnapshots ?? []; return search.isEmpty ? all : all.filter { $0.code.contains(search) || $0.name.localizedCaseInsensitiveContains(search) } }
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            PageHeading(title: "銘柄調査", subtitle: "業績の伸びと信用需給を横断比較")
            NoticeView(icon: "exclamationmark.triangle", text: "信用倍率が高く買残も増えている場合、好決算でも戻り売りが出やすくなります。未取得値は推測せず -- で表示します。")
            Table(rows) {
                TableColumn("銘柄") { StockName(name: $0.name, code: $0.code) }.width(min: 160, ideal: 220)
                TableColumn("売上成長") { Text(signedPercent($0.revenueYoy)).monospacedDigit() }.width(80)
                TableColumn("営利成長") { Text(signedPercent($0.operatingProfitYoy)).monospacedDigit() }.width(80)
                TableColumn("営利率") { Text(percent1($0.operatingMargin)).monospacedDigit() }.width(70)
                TableColumn("信用買残") { Text(compactNumber($0.longMarginOutstanding)).monospacedDigit() }.width(90)
                TableColumn("信用売残") { Text(compactNumber($0.shortMarginOutstanding)).monospacedDigit() }.width(90)
                TableColumn("信用倍率") { Text(ratioText($0.marginRatio)).foregroundStyle(marginColor($0.marginRatio)) }.width(75)
                TableColumn("買残前週比") { Text(signedPercent($0.longWeeklyChange)).monospacedDigit() }.width(90)
                TableColumn("基準日") { Text($0.marginAsOfDate ?? "--") }.width(90)
            }.searchable(text: $search, prompt: "銘柄名・コード")
        }.padding(26)
    }
}

struct SettingsView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                PageHeading(title: "設定・接続", subtitle: "自動運転の状態確認と保守操作")
                RunBanner()
                VStack(alignment: .leading, spacing: 12) {
                    Text("自動スケジュール").font(.headline)
                    ScheduleRow(icon: "sun.max", title: "候補生成とSlack通知", schedule: "平日 8:30 / 失敗時 8:45・9:00", action: model.runMorning)
                    ScheduleRow(icon: "checkmark.seal", title: "翌営業日の結果評価", schedule: "平日 15:45", action: model.runEvaluation)
                    ScheduleRow(icon: "calendar", title: "週次レビュー", schedule: "金曜 18:00", action: model.runWeeklyReview)
                }
                HStack(alignment: .top, spacing: 12) {
                    MaintenanceButton(title: "Slack接続テスト", detail: "テスト通知を1件送信", icon: "paperplane", action: model.runSlackTest)
                    MaintenanceButton(title: "学習を更新", detail: "30件以上で重みを補正", icon: "brain.head.profile", action: model.runLearning)
                    MaintenanceButton(title: "データを同期", detail: "GitHubの最新結果を取得", icon: "arrow.triangle.2.circlepath", action: model.syncLatest)
                }.disabled(model.isRunning)
                if let learning = model.data?.learning {
                    NoticeView(icon: "brain", text: "学習状態: \(learningLabel(learning.status)) / \(learning.sampleCount)件。\(learning.message ?? "")")
                }
                DisclosureGroup("実行ログ") {
                    Text(model.commandLog.isEmpty ? "このアプリからの実行履歴はまだありません。" : model.commandLog)
                        .font(.system(.caption, design: .monospaced)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading).padding(.top, 8)
                }
            }.padding(26)
        }
    }
}

struct StatusFooter: View { @EnvironmentObject private var model: AppModel; var body: some View { HStack(spacing: 8) { Circle().fill(model.lastError == nil ? Color.green : Color.red).frame(width: 8, height: 8); Text(model.statusMessage).font(.caption).lineLimit(2) }.frame(maxWidth: .infinity, alignment: .leading) } }
struct RunBanner: View { @EnvironmentObject private var model: AppModel; var body: some View { if model.isRunning { HStack(spacing: 10) { ProgressView(); Text(model.statusMessage).fontWeight(.medium); Spacer() }.padding(12).background(Color.blue.opacity(0.08), in: RoundedRectangle(cornerRadius: 6)) } else if let error = model.lastError { NoticeView(icon: "xmark.octagon.fill", text: error, color: .red) } } }
struct NotificationBand: View { let status: NotificationStatus?; var body: some View { HStack(spacing: 10) { Image(systemName: status?.status == "sent" ? "paperplane.circle.fill" : "exclamationmark.circle.fill").foregroundStyle(status?.status == "sent" ? Color.green : Color.orange); Text(notificationText(status)).font(.callout); Spacer(); Text(status?.createdAt.prefix(16).replacingOccurrences(of: "T", with: " ") ?? "").font(.caption.monospacedDigit()).foregroundStyle(.secondary) }.padding(.vertical, 10).overlay(alignment: .bottom) { Divider() } } }
struct PageHeading: View { let title, subtitle: String; var body: some View { VStack(alignment: .leading, spacing: 4) { Text(title).font(.largeTitle.bold()); Text(subtitle).foregroundStyle(.secondary) } } }
struct NoticeView: View { let icon, text: String; var color: Color = .blue; var body: some View { Label(text, systemImage: icon).font(.callout).foregroundStyle(.secondary).padding(12).frame(maxWidth: .infinity, alignment: .leading).background(color.opacity(0.08), in: RoundedRectangle(cornerRadius: 6)) } }
struct MetricTile: View { let label, value, detail: String; let color: Color; var body: some View { VStack(alignment: .leading, spacing: 6) { Text(label).font(.caption.bold()).foregroundStyle(.secondary); Text(value).font(.system(size: 25, weight: .bold, design: .rounded)).monospacedDigit().foregroundStyle(color); Text(detail).font(.caption).foregroundStyle(.secondary) }.padding(14).frame(maxWidth: .infinity, alignment: .leading).panelStyle() } }
struct ScheduleRow: View { let icon, title, schedule: String; let action: () -> Void; var body: some View { HStack(spacing: 12) { Image(systemName: icon).frame(width: 24).foregroundStyle(.blue); Text(title).fontWeight(.medium); Spacer(); Text(schedule).font(.callout).foregroundStyle(.secondary); Button { action() } label: { Image(systemName: "play.fill") }.buttonStyle(.borderless).help("今すぐ実行") }.padding(.vertical, 10).overlay(alignment: .bottom) { Divider() } } }
struct MaintenanceButton: View { let title, detail, icon: String; let action: () -> Void; var body: some View { Button(action: action) { VStack(alignment: .leading, spacing: 8) { Image(systemName: icon).font(.title2).foregroundStyle(.blue); Text(title).font(.headline); Text(detail).font(.caption).foregroundStyle(.secondary) }.padding(15).frame(maxWidth: .infinity, minHeight: 110, alignment: .leading).panelStyle() }.buttonStyle(.plain) } }
struct Fact: View { let icon, text: String; var body: some View { Label(text, systemImage: icon).font(.caption).foregroundStyle(.secondary) } }
struct TagLine: View { let title: String; let values: [String]; let color: Color; var body: some View { HStack(alignment: .top, spacing: 8) { Text(title).font(.caption.bold()).foregroundStyle(color).frame(width: 42, alignment: .leading); Text(values.joined(separator: " / ")).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) } } }
struct StockName: View { let name, code: String; var body: some View { VStack(alignment: .leading, spacing: 2) { Text(name).fontWeight(.medium); Text(code).font(.caption.monospacedDigit()).foregroundStyle(.secondary) } } }
struct ScoreBadge: View { let score: Int; var body: some View { Text("\(score)点").font(.caption.bold()).monospacedDigit().padding(.horizontal, 8).padding(.vertical, 4).background((score >= 80 ? Color.green : Color.blue).opacity(0.12), in: Capsule()).foregroundStyle(score >= 80 ? .green : .blue) } }
struct ResultBadge: View { let result: String; var body: some View { Text(result == "win" ? "勝ち" : result == "lose" ? "負け" : "中立").font(.caption.bold()).foregroundStyle(resultColor(result)) } }
struct LoadErrorView: View { @EnvironmentObject private var model: AppModel; var body: some View { ContentUnavailableView("データを読み込めません", systemImage: "exclamationmark.triangle", description: Text(model.lastError ?? "不明なエラー")) } }
extension View { func panelStyle() -> some View { background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 7)).overlay(RoundedRectangle(cornerRadius: 7).stroke(Color.primary.opacity(0.08))) } }

func notificationText(_ status: NotificationStatus?) -> String { guard let status else { return "Slack通知の実行履歴がありません" }; if status.status == "sent" { return "\(status.date) のSlack通知は送信済み（候補 \(status.candidateCount ?? 0)銘柄）" }; return "\(status.date) のSlack通知に失敗しています" }
func learningLabel(_ value: String) -> String { value == "observing" ? "観測中" : value == "active" ? "学習中" : value == "not_run" ? "未実行" : value }
func confidenceLabel(_ value: String?) -> String { value == "high" ? "高" : value == "medium" ? "中" : value == "low" ? "低" : "--" }
func actionLabel(_ value: String) -> String { value == "strong_cross" ? "強く跨ぐ" : value == "cross" ? "跨ぐ" : value == "watch" ? "様子見" : "見送り" }
func actionColor(_ value: String) -> Color { value == "strong_cross" ? .green : value == "cross" ? .blue : value == "watch" ? .orange : .secondary }
func percent(_ value: Double?) -> String { guard let value else { return "--" }; return value.formatted(.percent.precision(.fractionLength(0))) }
func signedPercent(_ value: Double?) -> String { guard let value else { return "--" }; return value.formatted(.percent.precision(.fractionLength(1)).sign(strategy: .always())) }
func percent1(_ value: Double?) -> String { guard let value else { return "--" }; return value.formatted(.percent.precision(.fractionLength(1))) }
func resultColor(_ result: String) -> Color { result == "win" ? .green : result == "lose" ? .red : .gray }
func returnColor(_ value: Double?) -> Color { guard let value else { return .secondary }; return value > 0 ? .green : value < 0 ? .red : .secondary }
func compactNumber(_ value: Double?) -> String { guard let value else { return "--" }; return value >= 10_000 ? String(format: "%.1f万", value / 10_000) : String(format: "%.0f", value) }
func ratioText(_ value: Double?) -> String { guard let value else { return "--" }; return String(format: "%.2f倍", value) }
func marginColor(_ value: Double?) -> Color { guard let value else { return .secondary }; return value >= 8 ? .red : value <= 3 ? .green : .primary }
func todayISO() -> String { let f = DateFormatter(); f.calendar = Calendar(identifier: .gregorian); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "Asia/Tokyo"); f.dateFormat = "yyyy-MM-dd"; return f.string(from: Date()) }
func todayDisplay() -> String { let f = DateFormatter(); f.locale = Locale(identifier: "ja_JP"); f.timeZone = TimeZone(identifier: "Asia/Tokyo"); f.dateFormat = "M月d日（E）"; return f.string(from: Date()) }
