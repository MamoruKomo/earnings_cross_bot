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
    enum CodingKeys: String, CodingKey {
        case generatedAt = "generated_at"; case summary
        case resultDistribution = "result_distribution"; case weekly
        case equityCurve = "equity_curve"; case byCode = "by_code"
        case recentOutcomes = "recent_outcomes"; case pendingRecommendations = "pending_recommendations"
        case stockSnapshots = "stock_snapshots"; case learning
    }
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
    enum CodingKeys: String, CodingKey {
        case code, name, score, action; case recommendationDate = "recommendation_date"; case eventDate = "event_date"
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

enum AppSection: String, CaseIterable, Identifiable {
    case overview = "概要"; case history = "推奨履歴"; case stocks = "銘柄別成績"; case analysis = "ファンダ・需給"; case operations = "運用"
    var id: String { rawValue }
    var icon: String { switch self { case .overview: "chart.xyaxis.line"; case .history: "clock.arrow.circlepath"; case .stocks: "building.2"; case .analysis: "scale.3d"; case .operations: "gearshape.2" } }
}
