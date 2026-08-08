import Foundation

struct DashboardData: Codable {
    let generatedAt: String
    let summary: Summary
    let resultDistribution: ResultDistribution
    let weekly: [WeeklyResult]
    let equityCurve: [EquityPoint]
    let byCode: [CodeResult]
    let recentOutcomes: [Outcome]
    let pendingRecommendations: [PendingRecommendation]
    let stockSnapshots: [StockSnapshot]
    let learning: LearningStatus
    let validation: ValidationReport
    let latestNotification: NotificationStatus?
    let marketIntelligence: MarketIntelligence?
    let daytrade: DaytradeDashboard?
    let decisionCenter: DecisionCenter?
    enum CodingKeys: String, CodingKey {
        case generatedAt = "generated_at"; case summary
        case resultDistribution = "result_distribution"; case weekly
        case equityCurve = "equity_curve"; case byCode = "by_code"
        case recentOutcomes = "recent_outcomes"; case pendingRecommendations = "pending_recommendations"
        case stockSnapshots = "stock_snapshots"; case learning, validation; case latestNotification = "latest_notification"
        case marketIntelligence = "market_intelligence"; case daytrade; case decisionCenter = "decision_center"
    }
}

struct DecisionCenter: Codable {
    let date, generatedAt, state, marketNote, noTradeReason, nextStep, modelStatus: String?
    let notificationStatus, dataStatus: String?
    let recommendations, considered: [DecisionCandidate]
    let scoredCount, eligibleCount: Int
    enum CodingKeys: String, CodingKey {
        case date, state, recommendations, considered
        case generatedAt = "generated_at"; case marketNote = "market_note"; case noTradeReason = "no_trade_reason"
        case nextStep = "next_step"; case modelStatus = "model_status"; case notificationStatus = "notification_status"
        case dataStatus = "data_status"; case scoredCount = "scored_count"; case eligibleCount = "eligible_count"
    }
}

struct DecisionCandidate: Codable, Identifiable {
    var id: String { code }
    let code, name, action, announcementTime, announcementTimeSource, thesis, dataQuality: String
    let score: Int
    let selected: Bool
    let confidence: String?
    let positiveFactors, riskFactors, missingData: [String]
    let components, contextAdjustments: [String: Double]
    let sector: DecisionSector
    let chart: DecisionChart
    let previousEarnings: PreviousEarnings
    let fundamentals: DecisionFundamentals
    let supplyDemand: DecisionSupplyDemand
    enum CodingKeys: String, CodingKey {
        case code, name, score, action, selected, confidence, thesis, components, sector, chart, fundamentals
        case announcementTime = "announcement_time"; case announcementTimeSource = "announcement_time_source"
        case positiveFactors = "positive_factors"; case riskFactors = "risk_factors"; case missingData = "missing_data"
        case dataQuality = "data_quality"; case contextAdjustments = "context_adjustments"
        case previousEarnings = "previous_earnings"; case supplyDemand = "supply_demand"
    }
}

struct DecisionSector: Codable { let name, mood, summary: String }
struct DecisionChart: Codable {
    let summary, trend: String
    let return5d, return20d, distanceFromHigh, volumeRatio: Double?
    enum CodingKeys: String, CodingKey {
        case summary, trend; case return5d = "return_5d"; case return20d = "return_20d"
        case distanceFromHigh = "distance_from_high"; case volumeRatio = "volume_ratio"
    }
}
struct PreviousEarnings: Codable {
    let summary, direction: String
    let previousCloseReturn: Double?
    enum CodingKeys: String, CodingKey { case summary, direction; case previousCloseReturn = "previous_close_return" }
}
struct DecisionFundamentals: Codable {
    let revenueYoy, operatingProfitYoy, revisionScore: Double?
    enum CodingKeys: String, CodingKey { case revenueYoy = "revenue_yoy"; case operatingProfitYoy = "operating_profit_yoy"; case revisionScore = "revision_score" }
}
struct DecisionSupplyDemand: Codable {
    let marginRatio, longWeeklyChange: Double?
    enum CodingKeys: String, CodingKey { case marginRatio = "margin_ratio"; case longWeeklyChange = "long_weekly_change" }
}

struct DaytradeDashboard: Codable {
    let candidates: [DaytradeCandidate]
    let outcomes: [DaytradeOutcome]
    let summary: DaytradeSummary
}

struct DaytradeSummary: Codable {
    let evaluated, targetHits: Int
    let hitRate: Double?
    enum CodingKeys: String, CodingKey { case evaluated; case targetHits = "target_hits"; case hitRate = "hit_rate" }
}

struct DaytradeCandidate: Codable, Identifiable {
    let id, rank, score: Int
    let tradeDate, code, name, theme: String
    let features: DaytradeFeatures
    let comment: DaytradeComment
    enum CodingKeys: String, CodingKey { case id, rank, score, code, name, theme, features, comment; case tradeDate = "trade_date" }
}

struct DaytradeFeatures: Codable {
    let price, changeRate, gapRate, volume, volumeRatio, turnover, vwap, atrRate, rsi: Double?
    let aboveVwap, breakout20d, boxBreakout: Bool?
    enum CodingKeys: String, CodingKey {
        case price, volume, turnover, vwap, rsi; case changeRate = "change_rate"; case gapRate = "gap_rate"
        case volumeRatio = "volume_ratio"; case atrRate = "atr_rate"; case aboveVwap = "above_vwap"
        case breakout20d = "breakout_20d"; case boxBreakout = "box_breakout"
    }
}

struct DaytradeComment: Codable {
    let reasons, risks: [String]
    let entryStrategy: String
    let takeProfit, stopLoss: Double?
    enum CodingKeys: String, CodingKey { case reasons, risks; case entryStrategy = "entry_strategy"; case takeProfit = "take_profit"; case stopLoss = "stop_loss" }
}

struct DaytradeOutcome: Codable, Identifiable {
    let id, candidateId, targetHit, stopHit: Int
    let tradeDate, code: String
    let referencePrice, high, low, close, maxUp, maxDown, closeReturn: Double?
    enum CodingKeys: String, CodingKey {
        case id, code, high, low, close; case candidateId = "candidate_id"; case targetHit = "target_hit"; case stopHit = "stop_hit"
        case tradeDate = "trade_date"; case referencePrice = "reference_price"; case maxUp = "max_up"; case maxDown = "max_down"; case closeReturn = "close_return"
    }
}

struct MarketIntelligence: Codable {
    let updatedAt: String?
    let latestBrief: MarketBrief?
    let recentBriefs: [MarketBrief]
    let latestWatchlist: WatchlistSnapshot?
    let fundamentals: FundamentalsSummary?
    let health: MarketHealth?
    enum CodingKeys: String, CodingKey {
        case updatedAt = "updated_at"; case latestBrief = "latest_brief"; case recentBriefs = "recent_briefs"
        case latestWatchlist = "latest_watchlist"; case fundamentals; case health
    }
}

struct MarketHealth: Codable {
    let overall: String
    let sources: [SourceHealth]
}

struct SourceHealth: Codable, Identifiable {
    var id: String { key }
    let key, label, status: String
    let updatedAt: String?
    let ageHours: Double?
    let message: String
    enum CodingKeys: String, CodingKey {
        case key, label, status, message; case updatedAt = "updated_at"; case ageHours = "age_hours"
    }
}

struct MarketBrief: Codable, Identifiable {
    var id: String { date }
    let date, headline: String
    let summaryBullets, tickers, tags: [String]
    enum CodingKeys: String, CodingKey {
        case date, headline, tickers, tags; case summaryBullets = "summary_bullets"
    }
}

struct WatchlistSnapshot: Codable {
    let datetimeJst, phase: String
    let items: [WatchlistItem]
    enum CodingKeys: String, CodingKey { case datetimeJst = "datetime_jst"; case phase, items }
}

struct WatchlistItem: Codable, Identifiable {
    var id: String { code }
    let code, name, sector: String
    let previousClose, open, close, volume: Double?
    enum CodingKeys: String, CodingKey {
        case code, name, sector, open, close, volume; case previousClose = "prev_close"
    }
}

struct FundamentalsSummary: Codable {
    let month, generatedAt: String?
    enum CodingKeys: String, CodingKey { case month; case generatedAt = "generated_at" }
}

struct Summary: Codable {
    let recommendationCount, evaluatedCount, pendingCount, noTradeDayCount: Int
    let winCount, neutralCount, loseCount: Int
    let hitRate, nonLossRate, avgNextOpenReturn, avgNextCloseReturn, positiveCloseRate: Double?
    enum CodingKeys: String, CodingKey {
        case recommendationCount = "recommendation_count"; case evaluatedCount = "evaluated_count"
        case pendingCount = "pending_count"; case noTradeDayCount = "no_trade_day_count"
        case winCount = "win_count"; case neutralCount = "neutral_count"; case loseCount = "lose_count"
        case hitRate = "hit_rate"; case nonLossRate = "non_loss_rate"
        case avgNextOpenReturn = "avg_next_open_return"; case avgNextCloseReturn = "avg_next_close_return"
        case positiveCloseRate = "positive_close_rate"
    }
}

struct ResultDistribution: Codable { let win, neutral, lose: Int }

struct WeeklyResult: Codable, Identifiable {
    var id: String { weekStart }
    let weekStart: String; let count, win, neutral, lose: Int
    let hitRate, avgNextCloseReturn: Double?
    enum CodingKeys: String, CodingKey {
        case weekStart = "week_start"; case count, win, neutral, lose
        case hitRate = "hit_rate"; case avgNextCloseReturn = "avg_next_close_return"
    }
}

struct EquityPoint: Codable, Identifiable {
    var id: String { "\(date)-\(code)" }
    let date, code, result: String; let nextCloseReturn, cumulativeReturn: Double
    enum CodingKeys: String, CodingKey {
        case date, code, result; case nextCloseReturn = "next_close_return"; case cumulativeReturn = "cumulative_return"
    }
}

struct CodeResult: Codable, Identifiable {
    var id: String { code }
    let code, name: String; let recommendationCount, evaluatedCount, win, neutral, lose: Int
    let hitRate, avgNextCloseReturn: Double?; let lastRecommendationDate: String
    enum CodingKeys: String, CodingKey {
        case code, name, win, neutral, lose; case recommendationCount = "recommendation_count"
        case evaluatedCount = "evaluated_count"; case hitRate = "hit_rate"
        case avgNextCloseReturn = "avg_next_close_return"; case lastRecommendationDate = "last_recommendation_date"
    }
}

struct Outcome: Codable, Identifiable {
    var id: String { "\(evaluationDate)-\(code)" }
    let recommendationDate, evaluationDate, code, name: String
    let score: Int; let action, result: String
    let nextOpenReturn, nextCloseReturn, maxDrawdown: Double?
    enum CodingKeys: String, CodingKey {
        case code, name, score, action, result; case recommendationDate = "recommendation_date"
        case evaluationDate = "evaluation_date"; case nextOpenReturn = "next_open_return"
        case nextCloseReturn = "next_close_return"; case maxDrawdown = "max_drawdown"
    }
}

struct PendingRecommendation: Codable, Identifiable {
    var id: String { "\(eventDate)-\(code)" }
    let recommendationDate, eventDate, code, name: String; let score: Int; let action: String
    let confidence, announcementTime, thesis: String?
    let riskFactors, missingData: [String]
    enum CodingKeys: String, CodingKey {
        case code, name, score, action, confidence, thesis
        case recommendationDate = "recommendation_date"; case eventDate = "event_date"
        case announcementTime = "announcement_time"; case riskFactors = "risk_factors"; case missingData = "missing_data"
    }
}

struct StockSnapshot: Codable, Identifiable {
    var id: String { code }
    let code, name: String
    let revenueYoy, operatingProfitYoy, operatingMargin, revenueProgressRate: Double?
    let financialSource, marginAsOfDate: String?
    let longMarginOutstanding, shortMarginOutstanding, marginRatio, longWeeklyChange: Double?
    let supplyDemandSource: String?
    enum CodingKeys: String, CodingKey {
        case code, name; case revenueYoy = "revenue_yoy"; case operatingProfitYoy = "operating_profit_yoy"
        case operatingMargin = "operating_margin"; case revenueProgressRate = "revenue_progress_rate"
        case financialSource = "financial_source"; case marginAsOfDate = "margin_as_of_date"
        case longMarginOutstanding = "long_margin_outstanding"; case shortMarginOutstanding = "short_margin_outstanding"
        case marginRatio = "margin_ratio"; case longWeeklyChange = "long_weekly_change"
        case supplyDemandSource = "supply_demand_source"
    }
}

struct LearningStatus: Codable {
    let status: String; let sampleCount: Int; let minimumSamples: Int?; let message: String?
    enum CodingKeys: String, CodingKey { case status, message; case sampleCount = "sample_count"; case minimumSamples = "minimum_samples" }
}

struct NotificationStatus: Codable {
    let date, type, status, createdAt: String
    let candidateCount: Int?; let dataStatus: String?
    enum CodingKeys: String, CodingKey {
        case date, type, status; case createdAt = "created_at"
        case candidateCount = "candidate_count"; case dataStatus = "data_status"
    }
}

struct ValidationReport: Codable {
    let status, message: String
    let sampleCount, trainingCount, holdoutCount, requiredCount: Int
    let all, holdout: ValidationMetrics
    let scoreBands: [ScoreBand]
    enum CodingKeys: String, CodingKey {
        case status, message, all, holdout; case sampleCount = "sample_count"; case trainingCount = "training_count"
        case holdoutCount = "holdout_count"; case requiredCount = "required_count"; case scoreBands = "score_bands"
    }
}

struct ValidationMetrics: Codable {
    let count, correct: Int
    let precision, precisionLower95, precisionUpper95, avgNextCloseReturn, positiveRate: Double?
    enum CodingKeys: String, CodingKey {
        case count, correct, precision; case precisionLower95 = "precision_lower_95"; case precisionUpper95 = "precision_upper_95"
        case avgNextCloseReturn = "avg_next_close_return"; case positiveRate = "positive_rate"
    }
}

struct ScoreBand: Codable, Identifiable {
    var id: String { band }
    let band: String; let count, correct: Int; let precision, avgNextCloseReturn: Double?
    enum CodingKeys: String, CodingKey { case band, count, correct, precision; case avgNextCloseReturn = "avg_next_close_return" }
}

enum AppSection: String, CaseIterable, Identifiable {
    case overview = "判断センター"; case history = "成績・学習"; case analysis = "銘柄比較"
    case morningBrief = "市場環境"; case watchlist = "ウォッチ"; case daytrade = "デイトレ"; case operations = "運用"
    var id: String { rawValue }
    var icon: String { switch self {
        case .overview: "sun.max"; case .daytrade: "bolt.horizontal.circle"; case .morningBrief: "newspaper"
        case .watchlist: "list.bullet.rectangle"; case .history: "checkmark.seal"
        case .analysis: "magnifyingglass"; case .operations: "gearshape"
    } }
}
