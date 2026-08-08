import Charts
import SwiftUI

struct RootView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        NavigationSplitView {
            VStack(spacing: 0) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("EARNINGS CROSS").font(.caption.bold()).foregroundStyle(.secondary)
                    Text("決算判断マネージャー").font(.title3.weight(.semibold))
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
                case .daytrade: DaytradeView()
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

struct DaytradeView: View {
    @EnvironmentObject private var model: AppModel
    var dashboard: DaytradeDashboard? { model.data?.daytrade }
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack(alignment: .top) {
                    PageHeading(title: "デイトレ", subtitle: "8:50時点の流動性・材料・テクニカルランキング")
                    Spacer()
                    Button { model.runDaytradeEvaluation() } label: { Label("結果評価", systemImage: "checkmark.seal") }.disabled(model.isRunning)
                    Button { model.runDaytradeRanking() } label: { Label("ランキング更新", systemImage: "bolt.fill") }.buttonStyle(.borderedProminent).disabled(model.isRunning)
                }
                RunBanner()
                NoticeView(icon: "clock", text: "平日8:50にSlackへ投稿し、15:50に当日高値・安値・終値を検証します。板・PTSなど未取得データは加点しません。", color: .cyan)
                if let summary = dashboard?.summary {
                    HStack(spacing: 12) {
                        MetricTile(label: "評価済み", value: "\(summary.evaluated)件", detail: "学習は40件から", color: .blue)
                        MetricTile(label: "+3%到達", value: "\(summary.targetHits)件", detail: "選定時価格から", color: .green)
                        MetricTile(label: "的中率", value: percent(summary.hitRate), detail: "最大上昇率基準", color: .indigo)
                    }
                }
                let rows = dashboard?.candidates ?? []
                if rows.isEmpty {
                    ContentUnavailableView("ランキング未生成", systemImage: "bolt.horizontal.circle", description: Text("ランキング更新を実行すると候補が表示されます。"))
                } else {
                    ForEach(rows.prefix(10)) { row in
                        VStack(alignment: .leading, spacing: 12) {
                            HStack { Text("\(row.rank)").font(.title.bold()).frame(width: 34); StockName(name: row.name.isEmpty ? row.code : row.name, code: row.code); Spacer(); Text(row.theme).font(.caption).foregroundStyle(.secondary); ScoreBadge(score: row.score) }
                            HStack(spacing: 18) {
                                Fact(icon: "yensign", text: priceText(row.features.price))
                                Fact(icon: "arrow.up.right", text: "GAP \(signedPercent(row.features.gapRate))")
                                Fact(icon: "chart.bar", text: "出来高 \(ratioTextPlain(row.features.volumeRatio))")
                                Fact(icon: "waveform.path.ecg", text: "ATR \(percent1(row.features.atrRate))")
                            }
                            Text(row.comment.reasons.joined(separator: " / ")).font(.callout)
                            Text("戦略: \(row.comment.entryStrategy)").font(.callout).foregroundStyle(.blue)
                            HStack { Text("利確 \(priceText(row.comment.takeProfit))"); Text("損切り \(priceText(row.comment.stopLoss))"); Spacer(); Text(row.comment.risks.joined(separator: " / ")).foregroundStyle(.orange) }.font(.caption)
                        }.padding(16).panelStyle()
                    }
                }
            }.padding(26)
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
                VStack(alignment: .leading, spacing: 18) {
                    HStack(alignment: .top) {
                        PageHeading(title: "決算跨ぎ 判断センター", subtitle: "候補、見送り理由、検証状況を一か所で確認")
                        Spacer()
                        Button { model.syncLatest() } label: { Label("最新データ", systemImage: "arrow.triangle.2.circlepath") }
                            .disabled(model.isRunning)
                    }
                    RunBanner()
                    if let center = data.decisionCenter {
                        DecisionStatusBand(center: center)
                        if center.recommendations.isEmpty {
                            DecisionEmptyState(center: center)
                        } else {
                            VStack(alignment: .leading, spacing: 10) {
                                SectionHeading(title: "推奨", detail: "最大3銘柄 / 発表時刻確認済み")
                                ForEach(center.recommendations) { DecisionCandidateView(item: $0) }
                            }
                        }
                        if !center.considered.isEmpty { ConsideredCandidates(items: center.considered) }
                    } else {
                        NoticeView(icon: "exclamationmark.triangle", text: "判断センターデータがありません。最新データへ同期してください。", color: .orange)
                    }
                    SectionHeading(title: "検証スナップショット", detail: "実データのみ")
                    HStack(spacing: 10) {
                        MetricTile(label: "評価済み", value: "\(data.summary.evaluatedCount)件", detail: "必要 \(data.validation.requiredCount)件", color: .blue)
                        MetricTile(label: "正答率", value: percent(data.summary.hitRate), detail: "95%下限 \(percent(data.validation.all.precisionLower95))", color: .green)
                        MetricTile(label: "非負け率", value: percent(data.summary.nonLossRate), detail: "勝ち＋中立", color: .teal)
                        MetricTile(label: "平均終値", value: signedPercent(data.summary.avgNextCloseReturn), detail: "翌営業日", color: .indigo)
                    }
                    RecentOutcomeBand(items: data.recentOutcomes)
                }.padding(26)
            } else { LoadErrorView() }
        }
    }
}

struct DecisionStatusBand: View {
    let center: DecisionCenter
    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: decisionStateIcon(center.state)).font(.system(size: 24, weight: .semibold)).foregroundStyle(decisionStateColor(center.state))
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 8) {
                    Text(decisionStateLabel(center.state)).font(.headline)
                    Text(center.date ?? "未実行").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                }
                Text(center.marketNote?.isEmpty == false ? center.marketNote! : "市場メモはありません").font(.callout).foregroundStyle(.secondary).lineLimit(2)
            }
            Spacer()
            StatusValue(label: "スキャン", value: "\(center.scoredCount)銘柄")
            StatusValue(label: "推奨", value: "\(center.eligibleCount)銘柄")
            StatusValue(label: "Slack", value: center.notificationStatus == "sent" ? "送信済み" : "未送信")
            Divider().frame(height: 34)
            VStack(alignment: .leading, spacing: 2) {
                Text("次の処理").font(.caption).foregroundStyle(.secondary)
                Text(center.nextStep ?? "--").font(.callout.bold())
            }.frame(minWidth: 150, alignment: .leading)
        }
        .padding(.horizontal, 16).padding(.vertical, 14)
        .background(decisionStateColor(center.state).opacity(0.07), in: RoundedRectangle(cornerRadius: 7))
        .overlay(RoundedRectangle(cornerRadius: 7).stroke(decisionStateColor(center.state).opacity(0.18)))
    }
}

struct DecisionEmptyState: View {
    let center: DecisionCenter
    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            Image(systemName: center.state == "data_unavailable" ? "wifi.exclamationmark" : "hand.raised.fill")
                .font(.system(size: 30)).foregroundStyle(center.state == "data_unavailable" ? .red : .orange).frame(width: 42)
            VStack(alignment: .leading, spacing: 6) {
                Text(center.state == "data_unavailable" ? "データ不足のため判定保留" : "今回は見送り").font(.title3.bold())
                Text(center.noTradeReason?.isEmpty == false ? center.noTradeReason! : "基準点、発表時刻、流動性、データ品質を満たす銘柄がありませんでした。")
                    .font(.callout).foregroundStyle(.secondary)
            }
        }.padding(18).frame(maxWidth: .infinity, alignment: .leading).panelStyle()
    }
}

struct DecisionCandidateView: View {
    let item: DecisionCandidate
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 14) {
                VStack(spacing: 1) {
                    Text("\(item.score)").font(.system(size: 29, weight: .bold, design: .rounded)).monospacedDigit()
                    Text("SCORE").font(.system(size: 9, weight: .bold)).foregroundStyle(.secondary)
                }.frame(width: 62, height: 54).background(actionColor(item.action).opacity(0.10), in: RoundedRectangle(cornerRadius: 6))
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) {
                        Text(item.name).font(.title3.bold())
                        Text(item.code).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                        Text(actionLabel(item.action)).font(.caption.bold()).foregroundStyle(actionColor(item.action))
                    }
                    Text(item.thesis.isEmpty ? "ルールスコアと安全条件を満たした候補です。" : item.thesis).font(.callout).foregroundStyle(.secondary).lineLimit(2)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 4) {
                    Label(item.announcementTime, systemImage: "clock.fill").font(.headline.monospacedDigit())
                    Text(timeSourceLabel(item.announcementTimeSource)).font(.caption).foregroundStyle(.secondary)
                }
            }
            Divider()
            HStack(alignment: .top, spacing: 0) {
                ContextColumn(icon: "chart.bar.xaxis", title: "セクター地合い", value: item.sector.summary, color: sectorMoodColor(item.sector.mood))
                Divider().frame(height: 50).padding(.horizontal, 14)
                ContextColumn(icon: "chart.xyaxis.line", title: "決算前チャート", value: item.chart.summary, color: trendColor(item.chart.trend))
                Divider().frame(height: 50).padding(.horizontal, 14)
                ContextColumn(icon: "arrow.triangle.2.circlepath", title: "前回決算比較", value: item.previousEarnings.summary, color: comparisonColor(item.previousEarnings.direction))
            }
            HStack(spacing: 18) {
                Fact(icon: "chart.line.uptrend.xyaxis", text: "営利成長 \(signedPercent(item.fundamentals.operatingProfitYoy))")
                Fact(icon: "arrow.up.forward", text: "修正期待 \(scoreText(item.fundamentals.revisionScore))")
                Fact(icon: "scale.3d", text: "信用倍率 \(ratioText(item.supplyDemand.marginRatio))")
                Fact(icon: "checkmark.shield", text: dataQualityLabel(item.dataQuality))
            }
            if !item.positiveFactors.isEmpty { TagLine(title: "根拠", values: item.positiveFactors, color: .green) }
            if !item.riskFactors.isEmpty { TagLine(title: "リスク", values: item.riskFactors, color: .orange) }
            if !item.missingData.isEmpty { TagLine(title: "欠損", values: item.missingData.map(dataFieldLabel), color: .gray) }
        }.padding(17).panelStyle()
    }
}

struct ContextColumn: View {
    let icon, title, value: String
    let color: Color
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Label(title, systemImage: icon).font(.caption.bold()).foregroundStyle(color)
            Text(value).font(.callout).fixedSize(horizontal: false, vertical: true).lineLimit(2)
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct ConsideredCandidates: View {
    let items: [DecisionCandidate]
    var body: some View {
        DisclosureGroup {
            VStack(spacing: 0) {
                ForEach(items) { item in
                    HStack(spacing: 12) {
                        ScoreBadge(score: item.score)
                        StockName(name: item.name, code: item.code)
                        Text(actionLabel(item.action)).font(.caption).foregroundStyle(actionColor(item.action)).frame(width: 58, alignment: .leading)
                        Text(item.riskFactors.first ?? item.missingData.first ?? "基準点未満").font(.caption).foregroundStyle(.secondary).lineLimit(1)
                        Spacer()
                        Text(item.announcementTime).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                    }.padding(.vertical, 8)
                    if item.id != items.last?.id { Divider() }
                }
            }.padding(.top, 8)
        } label: {
            HStack { Text("候補外の上位銘柄").font(.headline); Text("\(items.count)銘柄").font(.caption).foregroundStyle(.secondary) }
        }.padding(15).panelStyle()
    }
}

struct RecentOutcomeBand: View {
    let items: [Outcome]
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionHeading(title: "最近の検証", detail: "直近5件")
            HStack(spacing: 0) {
                ForEach(Array(items.prefix(5))) { item in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack { Text(item.code).font(.caption.monospacedDigit()); Spacer(); ResultBadge(result: item.result) }
                        Text(item.name).font(.callout.bold()).lineLimit(1)
                        Text(signedPercent(item.nextCloseReturn)).font(.title3.bold()).monospacedDigit().foregroundStyle(returnColor(item.nextCloseReturn))
                    }.padding(.horizontal, 12).frame(maxWidth: .infinity, alignment: .leading)
                    if item.id != items.prefix(5).last?.id { Divider().frame(height: 54) }
                }
            }.padding(.vertical, 12).panelStyle()
        }
    }
}

struct SectionHeading: View { let title, detail: String; var body: some View { HStack(alignment: .firstTextBaseline) { Text(title).font(.title3.bold()); Text(detail).font(.caption).foregroundStyle(.secondary); Spacer() } } }
struct StatusValue: View { let label, value: String; var body: some View { VStack(alignment: .leading, spacing: 2) { Text(label).font(.caption).foregroundStyle(.secondary); Text(value).font(.callout.bold()).monospacedDigit() }.frame(minWidth: 66, alignment: .leading) } }

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
                    ScheduleRow(icon: "bolt.horizontal.circle", title: "デイトレランキング", schedule: "平日 8:50", action: model.runDaytradeRanking)
                    ScheduleRow(icon: "newspaper", title: "市場朝刊", schedule: "平日 8:20", action: model.runMarketBrief)
                    ScheduleRow(icon: "list.bullet.rectangle", title: "ウォッチ", schedule: "平日 9:30・16:00", action: model.runWatchlist)
                    ScheduleRow(icon: "checkmark.seal", title: "翌営業日の結果評価", schedule: "平日 15:45", action: model.runEvaluation)
                    ScheduleRow(icon: "chart.xyaxis.line", title: "デイトレ結果評価", schedule: "平日 15:50", action: model.runDaytradeEvaluation)
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
func ratioTextPlain(_ value: Double?) -> String { guard let value else { return "--" }; return String(format: "%.1f倍", value) }
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
func decisionStateLabel(_ value: String?) -> String {
    switch value { case "awaiting_results": "推薦済み・結果待ち"; case "evaluation_overdue": "結果評価が遅延"; case "evaluated": "評価完了"; case "no_trade": "見送り"; case "data_unavailable": "判定保留"; default: "未実行" }
}
func decisionStateIcon(_ value: String?) -> String {
    switch value { case "awaiting_results": "clock.badge.checkmark"; case "evaluation_overdue": "exclamationmark.arrow.triangle.2.circlepath"; case "evaluated": "checkmark.seal.fill"; case "no_trade": "hand.raised.fill"; case "data_unavailable": "exclamationmark.triangle.fill"; default: "circle.dashed" }
}
func decisionStateColor(_ value: String?) -> Color {
    switch value { case "awaiting_results": .blue; case "evaluation_overdue": .red; case "evaluated": .green; case "no_trade": .orange; case "data_unavailable": .red; default: .gray }
}
func sectorMoodColor(_ value: String) -> Color { value == "strong" ? .green : value == "weak" ? .red : .secondary }
func trendColor(_ value: String) -> Color { value.contains("uptrend") ? .green : value.contains("downtrend") ? .red : .secondary }
func comparisonColor(_ value: String) -> Color { value == "improving" ? .green : value == "worsening" ? .red : .secondary }
func timeSourceLabel(_ value: String) -> String { value == "traders_web" ? "Traders Web" : value == "jquants" ? "J-Quants" : "時刻ソース不明" }
func scoreText(_ value: Double?) -> String { guard let value else { return "--" }; return String(format: "%.0f点", value) }
func dataQualityLabel(_ value: String) -> String { value == "complete" ? "データ充足" : value == "partial" ? "一部欠損" : "要注意" }
func dataFieldLabel(_ value: String) -> String {
    let labels = [
        "historical_earnings_reaction": "過去決算反応", "operating_margin_change": "利益率変化",
        "supply_demand": "信用需給", "sector_classification": "業種分類", "sector_mood": "セクター地合い",
        "financial_statement": "財務データ", "announcement_time_unknown": "発表時刻",
    ]
    return labels[value] ?? value
}
