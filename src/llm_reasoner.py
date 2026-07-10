from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any

import requests

from src import db


EVALUATION_RULE = "決算当日終値から翌営業日の始値・終値までの騰落率で評価する"


def generate_recommendation_payload(
    conn,
    target_date: date,
    selected_candidates: list[dict[str, Any]],
    all_scored: list[dict[str, Any]],
    rules: dict[str, Any],
) -> dict[str, Any]:
    model = str(rules.get("llm", {}).get("model", "gpt-4.1-mini"))
    prompt = build_recommendation_prompt(target_date, selected_candidates, all_scored)
    input_data = {
        "date": target_date.isoformat(),
        "selected_candidates": selected_candidates,
        "all_scored": all_scored,
        "rules_version": rules.get("version"),
    }
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        payload = fallback_recommendation_payload(target_date, selected_candidates, all_scored)
        db.insert_llm_run(conn, "recommendation", model, prompt, input_data, payload, "fallback_no_api_key")
        return payload

    try:
        payload = call_openai_json(api_key, model, prompt, input_data, rules)
        db.insert_llm_run(conn, "recommendation", model, prompt, input_data, payload, "success")
        return payload
    except Exception as exc:  # noqa: BLE001 - capture external API failures for audit.
        payload = fallback_recommendation_payload(target_date, selected_candidates, all_scored)
        db.insert_llm_run(conn, "recommendation", model, prompt, input_data, payload, "fallback_error", str(exc))
        return payload


def build_recommendation_prompt(
    target_date: date,
    selected_candidates: list[dict[str, Any]],
    all_scored: list[dict[str, Any]],
) -> str:
    return (
        "あなたは日本株の決算跨ぎ候補を検証用に説明するアナリストです。"
        "投資助言ではなく、ルールスコアの理由をJSONだけで返してください。"
        "必ず候補なしを許可し、無理に銘柄を選ばないでください。"
        "観点: 決算が良さそうか、織り込み済みか、決算前に上がりすぎていないか、"
        "流動性、過去決算後反応、相場テーマ、信用買残・売残・信用倍率、悪材料や出尽くしリスク。"
        "\n\n"
        f"日付: {target_date.isoformat()}\n"
        f"投稿候補: {json.dumps(selected_candidates, ensure_ascii=False)}\n"
        f"全スコア: {json.dumps(all_scored, ensure_ascii=False)}\n\n"
        "出力JSON形式: {\"date\":\"YYYY-MM-DD\",\"market_note\":\"...\","
        "\"recommendations\":[{\"code\":\"1234\",\"name\":\"会社名\",\"score\":78,"
        "\"action\":\"cross\",\"confidence\":\"medium\",\"announcement_time\":\"15:00以降\","
        "\"thesis\":\"...\",\"positive_factors\":[\"...\"],\"risk_factors\":[\"...\"],"
        "\"expected_reaction\":\"...\",\"evaluation_rule\":\"...\",\"missing_data\":[\"...\"]}],"
        "\"no_trade_reason\":\"候補がない場合は理由\"}"
    )


def call_openai_json(
    api_key: str,
    model: str,
    prompt: str,
    input_data: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    timeout = int(rules.get("llm", {}).get("timeout_seconds", 45))
    max_retries = int(rules.get("llm", {}).get("max_retries", 2))
    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Return valid JSON only. No markdown."},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return parse_json_content(content)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"OpenAI JSON generation failed: {last_error}")


def parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM output was not a JSON object")
    return parsed


def fallback_recommendation_payload(
    target_date: date,
    selected_candidates: list[dict[str, Any]],
    all_scored: list[dict[str, Any]],
) -> dict[str, Any]:
    if not selected_candidates:
        best = max((row.get("score", 0) for row in all_scored), default=0)
        return {
            "date": target_date.isoformat(),
            "market_note": "70点以上の候補がないため、無理な決算跨ぎは避ける判定です。",
            "recommendations": [],
            "no_trade_reason": f"最高スコアが{best}点で基準未満でした。候補なしを正常出力として扱います。",
        }

    recommendations = []
    for item in selected_candidates:
        recommendations.append(
            {
                "code": item["code"],
                "name": item.get("name", ""),
                "score": int(item.get("score", 0)),
                "action": item.get("action", "cross"),
                "confidence": confidence_for_score(int(item.get("score", 0))),
                "announcement_time": item.get("announcement_time") or "不明",
                "thesis": build_thesis(item),
                "positive_factors": positive_factors(item),
                "risk_factors": risk_factors(item),
                "expected_reaction": expected_reaction(item),
                "evaluation_rule": EVALUATION_RULE,
                "missing_data": item.get("missing_data", []),
            }
        )
    return {
        "date": target_date.isoformat(),
        "market_note": "ルールスコアで70点以上の銘柄に限定し、過熱感と流動性を確認したうえで候補化しています。",
        "recommendations": recommendations,
        "no_trade_reason": "",
    }


def confidence_for_score(score: int) -> str:
    if score >= 82:
        return "high"
    if score >= 70:
        return "medium"
    return "low"


def build_thesis(item: dict[str, Any]) -> str:
    components = item.get("components", {})
    strongest = sorted(components.items(), key=lambda pair: pair[1], reverse=True)[:2]
    labels = "、".join(key for key, _ in strongest)
    return f"総合スコア{item.get('score')}点。主に{labels}が評価され、決算跨ぎ候補として残りました。"


def positive_factors(item: dict[str, Any]) -> list[str]:
    financial = item.get("financial_features", {})
    price = item.get("price_features", {})
    reaction = item.get("reaction_features", {})
    demand = item.get("supply_demand_features", {})
    factors = []
    if financial.get("operating_profit_yoy") is not None:
        factors.append(f"営業利益前年同期比が{financial['operating_profit_yoy']:.1%}で成長評価がある")
    if financial.get("revision_expectation_score") is not None:
        factors.append(f"上方修正期待スコアが{financial['revision_expectation_score']:.1f}点")
    if price.get("return_20d") is not None:
        factors.append(f"決算前20営業日リターンは{price['return_20d']:.1%}で過熱感を確認済み")
    if reaction.get("positive_reaction_ratio") is not None:
        factors.append(f"過去決算後の陽性反応比率は{reaction['positive_reaction_ratio']:.0%}")
    if demand.get("margin_ratio") is not None and demand["margin_ratio"] <= 3:
        factors.append(f"信用倍率は{demand['margin_ratio']:.2f}倍で需給負担が比較的軽い")
    return factors[:3] or ["ルールスコアが基準を上回った"]


def risk_factors(item: dict[str, Any]) -> list[str]:
    flags = list(item.get("risk_flags") or [])
    demand = item.get("supply_demand_features", {})
    if demand.get("margin_ratio") is not None and demand["margin_ratio"] >= 8:
        flags.append(f"信用倍率が{demand['margin_ratio']:.2f}倍と高く、戻り売りリスク")
    if demand.get("long_weekly_change") is not None and demand["long_weekly_change"] >= 0.10:
        flags.append(f"信用買残が前週比{demand['long_weekly_change']:.1%}増加")
    if item.get("missing_data"):
        flags.append("不足データがあるため確信度を抑制")
    if not flags:
        flags.append("好決算でも材料出尽くしになる可能性")
    return flags[:3]


def expected_reaction(item: dict[str, Any]) -> str:
    reaction = item.get("reaction_features", {})
    avg_close = reaction.get("avg_next_close_return")
    if avg_close is None:
        return "過去反応データが不足しており、翌営業日の値動きは中立に見る。"
    if avg_close > 0.02:
        return "好決算なら翌日買われやすい傾向。ただし寄り後の失速は検証対象。"
    if avg_close < -0.01:
        return "過去には決算後に売られやすく、出尽くしリスクを強めに見る。"
    return "過去反応は中立で、決算内容と地合いの影響を受けやすい。"


def analyze_outcome_lesson(recommendation: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    result = outcome["result"]
    return {
        "code": recommendation["code"],
        "result": result,
        "was_prediction_correct": result == "win",
        "reason_hit": "翌日始値または終値が+3%以上となり、決算跨ぎ候補として機能した。" if result == "win" else "",
        "reason_miss": "翌日反応が基準に届かなかった。過熱感、地合い、出尽くしリスクの見直しが必要。" if result != "win" else "",
        "missed_risks": recommendation.get("risk_factors", []),
        "features_to_watch_next": ["return_20d", "avg_turnover_20d", "historical_reaction", "revision_expectation_score"],
        "rule_change_idea": "週次レビューで閾値変更を検討し、本番rules.yamlは自動変更しない。",
    }
