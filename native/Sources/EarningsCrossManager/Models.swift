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
    enum CodingKeys: String, CodingKey {
        case generatedAt = "generated_at"; case summary
        case resultDistribution = "result_distribution"; case weekly
        case equityCurve = "equity_curve"; case byCode = "by_code"
        case recentOutcomes = "recent_outcomes"; case pendingRecommendations = "pending_recommendations"
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

enum AppSection: String, CaseIterable, Identifiable {
    case overview = "概要"; case history = "推奨履歴"; case stocks = "銘柄別成績"; case operations = "運用"
    var id: String { rawValue }
    var icon: String { switch self { case .overview: "chart.xyaxis.line"; case .history: "clock.arrow.circlepath"; case .stocks: "building.2"; case .operations: "gearshape.2" } }
}
