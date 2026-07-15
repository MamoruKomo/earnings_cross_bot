from __future__ import annotations

from typing import Any


def build_comment(candidate: dict[str, Any]) -> dict[str, Any]:
    f = candidate["features"]; news = candidate.get("news") or []; price = f.get("price"); atr = f.get("atr") or (price * 0.025 if price else 0)
    reasons = []
    if (f.get("volume_ratio") or 0) >= 1.5: reasons.append(f"出来高ペースが平常の{f['volume_ratio']:.1f}倍")
    if f.get("above_vwap"): reasons.append("株価がVWAPを上回る")
    if f.get("breakout_20d") or f.get("box_breakout"): reasons.append("直近レンジを上抜け")
    positive = [item["summary"] for item in news if item["sentiment"] == "positive"]
    if positive: reasons.append(f"好材料: {positive[0][:70]}")
    if not reasons: reasons.append("流動性・値幅・テクニカルの総合点が基準を上回る")
    entry = f"VWAP付近の押し目または朝高値更新で分割エントリー" if f.get("above_vwap") else "VWAP回復を確認するまで待機"
    target = price + atr if price else None
    technical_stop = price - atr * 0.65 if price else None
    vwap = f.get("vwap")
    stop = max(technical_stop, vwap) if technical_stop is not None and vwap is not None and vwap < price else technical_stop
    risks = []
    if (f.get("gap_rate") or 0) > 0.05: risks.append("ギャップ過大で寄り天に注意")
    if f.get("rsi") is not None and f["rsi"] >= 75: risks.append("RSI過熱")
    if any(item["sentiment"] == "negative" for item in news): risks.append("悪材料ニュースを含む")
    if "order_book" in f.get("unavailable", []): risks.append("板情報未取得のため約定前に気配確認必須")
    return {"reasons": reasons, "entry_strategy": entry, "take_profit": target, "stop_loss": stop, "risks": risks or ["地合い急変と出来高失速に注意"]}
