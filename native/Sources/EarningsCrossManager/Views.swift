import Charts
import SwiftUI

struct RootView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        NavigationSplitView {
            VStack(spacing: 0) {
                VStack(alignment: .leading, spacing: 3) {
                    Text("MARKET OPERATIONS").font(.caption.bold()).foregroundStyle(.secondary)
                    Text("Earnings Cross Manager").font(.title3.weight(.semibold))
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
                case .morningBrief: MorningBriefView()
                case .watchlist: WatchlistView()
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

struct MorningBriefView: View {
    @EnvironmentObject private var model: AppModel
    var briefs: [MarketBrief] { model.data?.marketIntelligence?.recentBriefs ?? [] }
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack(alignment: .top) {
                    PageHeading(title: "市況・朝刊", subtitle: "market-morning-briefの市場環境と注目銘柄")
                    Spacer()
                    Button { model.runMarketBrief() } label: { Label("朝刊を更新", systemImage: "arrow.clockwise") }
                        .disabled(model.isRunning)
                }
                RunBanner()
                SourceHealthBanner(sourceKey: "morning_brief")
                if briefs.isEmpty {
                    ContentUnavailableView("朝刊がありません", systemImage: "newspaper", description: Text("朝刊生成ジョブを実行してください。"))
                } else {
                    ForEach(briefs) { brief in
                        VStack(alignment: .leading, spacing: 10) {
                            HStack { Text(brief.date).font(.caption.monospacedDigit()).foregroundStyle(.secondary); Spacer(); Text(brief.tags.joined(separator: " / ")).font(.caption).foregroundStyle(.secondary) }
                            Text(brief.headline).font(.headline)
                            ForEach(brief.summaryBullets, id: \.self) { Text($0).font(.callout) }
                            if !brief.tickers.isEmpty { Text("注目: " + brief.tickers.joined(separator: ", ")).font(.caption.monospacedDigit()).foregroundStyle(.blue) }
                        }.padding(16).panelStyle()
                    }
                }
            }.padding(26)
        }
    }
}

struct WatchlistView: View {
    @EnvironmentObject private var model: AppModel
    @State private var search = ""
    var snapshot: WatchlistSnapshot? { model.data?.marketIntelligence?.latestWatchlist }
    var rows: [WatchlistItem] {
        let all = snapshot?.items ?? []
        return search.isEmpty ? all : all.filter { $0.code.contains(search) || $0.name.localizedCaseInsensitiveContains(search) || $0.sector.localizedCaseInsensitiveContains(search) }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top) {
                PageHeading(title: "ウォッチ", subtitle: snapshot.map { "\(shortDateTime($0.datetimeJst)) / \(watchPhaseLabel($0.phase))" } ?? "スナップショット未取得")
                Spacer()
                Button { model.runWatchlist() } label: { Label("引け値を更新", systemImage: "arrow.clockwise") }.disabled(model.isRunning)
            }
            RunBanner()
            SourceHealthBanner(sourceKey: "watchlist")
            Table(rows) {
                TableColumn("セクター", value: \.sector).width(90)
                TableColumn("銘柄") { StockName(name: $0.name, code: $0.code) }.width(min: 150, ideal: 210)
                TableColumn("価格") { Text(priceText($0.close ?? $0.open)).monospacedDigit() }.width(90)
                TableColumn("前日比") { Text(watchChange($0)).monospacedDigit().foregroundStyle(watchChangeColor($0)) }.width(90)
                TableColumn("出来高") { Text(compactNumber($0.volume)).monospacedDigit() }.width(100)
            }.searchable(text: $search, prompt: "銘柄・コード・セクター")
        }.padding(26)
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
                    MarketHealthBand()
                    NoticeView(icon: "shield.lefthalf.filled", text: "このアプリは判断支援用です。注文は行いません。発表時刻、データ欠損、損失リスクを確認して最終判断してください。", color: .indigo)
                    MarketOverviewPanel(market: data.marketIntelligence)
                    NotificationBand(status: data.latestNotification)
                    TodayCandidates(items: data.pendingRecommendations)
                    HStack(spacing: 12) {
                        MetricTile(label: "検証済み", value: "\(data.summary.evaluatedCount)件", detail: "時系列検証 40件", color: .blue)
                        MetricTile(label: "勝率", value: percent(data.summary.hitRate), detail: "勝ち \(data.summary.winCount) / 負け \(data.summary.loseCount)", color: .green)
                        MetricTile(label: "平均反応", value: signedPercent(data.summary.avgNextCloseReturn), detail: "翌営業日終値", color: .indigo)
                    }
                    if data.summary.evaluatedCount < data.validation.requiredCount {
                        NoticeView(icon: "hourglass", text: "まだ検証母数が少ないため、勝率は参考値です。あと \(data.validation.requiredCount - data.summary.evaluatedCount) 件で時系列検証を開始します。")
                    }
                }.padding(26)
            } else { LoadErrorView() }
        }
    }
}

struct MarketOverviewPanel: View {
    @EnvironmentObject private var model: AppModel
    let market: MarketIntelligence?
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Label("今日の市況", systemImage: "chart.line.uptrend.xyaxis").font(.title2.bold())
                Spacer()
                Button("市況・朝刊を開く") { model.selectedSection = .morningBrief }.buttonStyle(.borderless)
            }
            if let brief = market?.latestBrief {
                HStack(alignment: .firstTextBaseline) {
                    Text(brief.headline).font(.headline)
                    Spacer()
                    Text(brief.date).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                }
                ForEach(brief.summaryBullets, id: \.self) { bullet in
                    Label(bullet, systemImage: "circle.fill").font(.callout).symbolRenderingMode(.hierarchical)
                }
                if !brief.tickers.isEmpty {
                    HStack(alignment: .top, spacing: 8) {
                        Text("注目コード").font(.caption.bold()).foregroundStyle(.secondary)
                        Text(brief.tickers.prefix(8).joined(separator: "  ")).font(.caption.monospacedDigit()).textSelection(.enabled)
                    }
                }
            } else {
                Text("市況データがありません。市況・朝刊を更新してください。").foregroundStyle(.secondary)
            }
            Divider()
            HStack(spacing: 20) {
                MarketFact(icon: "list.bullet.rectangle", title: "ウォッチ", value: market?.latestWatchlist.map { shortDateTime($0.datetimeJst) } ?? "未取得") { model.selectedSection = .watchlist }
                Spacer()
                Button { model.runMarketBrief() } label: { Label("市況を更新", systemImage: "arrow.clockwise") }.disabled(model.isRunning)
            }
        }.padding(16).panelStyle()
    }
}

struct MarketFact: View {
    let icon, title, value: String
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: icon).foregroundStyle(.blue)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.caption).foregroundStyle(.secondary)
                    Text(value).font(.callout.bold()).monospacedDigit()
                }
            }
        }.buttonStyle(.plain)
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
                ValidationPanel(report: data.validation)
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
                MarketHealthBand(showSources: true)
                VStack(alignment: .leading, spacing: 12) {
                    Text("自動スケジュール").font(.headline)
                    ScheduleRow(icon: "sun.max", title: "候補生成とSlack通知", schedule: "平日 8:30 / 失敗時 8:45・9:00", action: model.runMorning)
                    ScheduleRow(icon: "newspaper", title: "市場朝刊", schedule: "平日 8:20", action: model.runMarketBrief)
                    ScheduleRow(icon: "list.bullet.rectangle", title: "ウォッチ", schedule: "平日 9:30・16:00", action: model.runWatchlist)
                    ScheduleRow(icon: "checkmark.seal", title: "翌営業日の結果評価", schedule: "平日 15:45", action: model.runEvaluation)
                    ScheduleRow(icon: "calendar", title: "週次レビュー", schedule: "金曜 18:00", action: model.runWeeklyReview)
                }
                HStack(alignment: .top, spacing: 12) {
                    MaintenanceButton(title: "Slack接続テスト", detail: "テスト通知を1件送信", icon: "paperplane", action: model.runSlackTest)
                    MaintenanceButton(title: "学習を更新", detail: "30件で学習・直近10件で検証", icon: "brain.head.profile", action: model.runLearning)
                    MaintenanceButton(title: "データを同期", detail: "最新スナップショットを取得", icon: "arrow.triangle.2.circlepath", action: model.syncLatest)
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

struct ValidationPanel: View {
    let report: ValidationReport
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("時系列検証").font(.headline)
                    Text(report.message).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Text(report.status == "ready" ? "検証可能" : "データ収集中").font(.caption.bold()).foregroundStyle(report.status == "ready" ? Color.green : Color.orange)
            }
            HStack(spacing: 20) {
                ValidationValue(label: "全期間正答率", value: percent(report.all.precision), detail: "\(report.all.correct)/\(report.all.count)件")
                ValidationValue(label: "未見データ正答率", value: percent(report.holdout.precision), detail: "直近 \(report.holdoutCount)件")
                ValidationValue(label: "95%信頼下限", value: percent(report.all.precisionLower95), detail: "偶然の上振れを考慮")
                ValidationValue(label: "必要件数", value: "\(report.sampleCount)/\(report.requiredCount)", detail: "学習30 + 検証10")
            }
            if !report.scoreBands.isEmpty {
                Divider()
                HStack { Text("スコア帯").font(.caption.bold()).foregroundStyle(.secondary); Spacer(); ForEach(report.scoreBands) { band in Text("\(band.band): \(percent(band.precision)) (\(band.count)件)").font(.caption.monospacedDigit()).frame(minWidth: 140, alignment: .trailing) } }
            }
        }.padding(16).panelStyle()
    }
}

struct ValidationValue: View { let label, value, detail: String; var body: some View { VStack(alignment: .leading, spacing: 3) { Text(label).font(.caption).foregroundStyle(.secondary); Text(value).font(.title3.bold()).monospacedDigit(); Text(detail).font(.caption2).foregroundStyle(.secondary) }.frame(maxWidth: .infinity, alignment: .leading) } }

struct StatusFooter: View { @EnvironmentObject private var model: AppModel; var body: some View { HStack(spacing: 8) { Circle().fill(statusColor(model.lastError == nil ? model.data?.marketIntelligence?.health?.overall : "error")).frame(width: 8, height: 8); Text(model.statusMessage).font(.caption).lineLimit(2) }.frame(maxWidth: .infinity, alignment: .leading) } }
struct RunBanner: View { @EnvironmentObject private var model: AppModel; var body: some View { if model.isRunning { HStack(spacing: 10) { ProgressView(); Text(model.statusMessage).fontWeight(.medium); Spacer() }.padding(12).background(Color.blue.opacity(0.08), in: RoundedRectangle(cornerRadius: 6)) } else if let error = model.lastError { NoticeView(icon: "xmark.octagon.fill", text: error, color: .red) } } }
struct MarketHealthBand: View {
    @EnvironmentObject private var model: AppModel
    var showSources = false
    var body: some View {
        if let health = model.data?.marketIntelligence?.health {
            VStack(alignment: .leading, spacing: 10) {
                Label(healthLabel(health.overall), systemImage: health.overall == "fresh" ? "checkmark.shield.fill" : "exclamationmark.triangle.fill")
                    .font(.callout.bold()).foregroundStyle(statusColor(health.overall))
                if showSources {
                    ForEach(health.sources) { source in
                        HStack(spacing: 10) {
                            Circle().fill(statusColor(source.status)).frame(width: 7, height: 7)
                            Text(source.label).fontWeight(.medium).frame(width: 125, alignment: .leading)
                            Text(source.message).foregroundStyle(.secondary)
                            Spacer()
                            Text(shortDateTime(source.updatedAt)).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                        }.font(.callout)
                    }
                }
            }.padding(12).frame(maxWidth: .infinity, alignment: .leading).background(statusColor(health.overall).opacity(0.08), in: RoundedRectangle(cornerRadius: 6))
        }
    }
}
struct SourceHealthBanner: View {
    @EnvironmentObject private var model: AppModel
    let sourceKey: String
    var body: some View {
        if let source = model.data?.marketIntelligence?.health?.sources.first(where: { $0.key == sourceKey }), source.status != "fresh" {
            NoticeView(icon: "exclamationmark.triangle.fill", text: "\(source.label): \(source.message)（最終更新 \(shortDateTime(source.updatedAt))）", color: statusColor(source.status))
        }
    }
}
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
func shortDateTime(_ value: String?) -> String { guard let value, !value.isEmpty else { return "--" }; return String(value.prefix(16)).replacingOccurrences(of: "T", with: " ") }
func priceText(_ value: Double?) -> String { guard let value else { return "--" }; return value.formatted(.number.precision(.fractionLength(value.rounded() == value ? 0 : 1))) }
func watchChangeValue(_ item: WatchlistItem) -> Double? { guard let price = item.close ?? item.open, let previous = item.previousClose, previous != 0 else { return nil }; return price / previous - 1 }
func watchChange(_ item: WatchlistItem) -> String { signedPercent(watchChangeValue(item)) }
func watchChangeColor(_ item: WatchlistItem) -> Color { returnColor(watchChangeValue(item)) }
func watchPhaseLabel(_ value: String) -> String { value == "open" ? "寄り" : "引け" }
func marginColor(_ value: Double?) -> Color { guard let value else { return .secondary }; return value >= 8 ? .red : value <= 3 ? .green : .primary }
func todayISO() -> String { let f = DateFormatter(); f.calendar = Calendar(identifier: .gregorian); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "Asia/Tokyo"); f.dateFormat = "yyyy-MM-dd"; return f.string(from: Date()) }
func todayDisplay() -> String { let f = DateFormatter(); f.locale = Locale(identifier: "ja_JP"); f.timeZone = TimeZone(identifier: "Asia/Tokyo"); f.dateFormat = "M月d日（E）"; return f.string(from: Date()) }
func statusColor(_ status: String?) -> Color { status == "fresh" ? .green : status == "warning" ? .orange : status == "stale" || status == "missing" || status == "error" ? .red : .gray }
func healthLabel(_ status: String) -> String { status == "fresh" ? "市場データは更新済みです" : status == "warning" ? "更新時刻に注意が必要なデータがあります" : "期限切れまたは欠損データがあります。数値を判断に使用しないでください" }
