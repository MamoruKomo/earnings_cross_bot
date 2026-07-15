from __future__ import annotations

from typing import Any

from src.slack_notifier import post_message


def format_ranking(payload: dict[str, Any]) -> str:
    lines = ["【デイトレ銘柄ランキング】", f"日付：{payload['date']}  8:50時点", ""]
    rows = payload.get("candidates") or []
    if not rows: return "\n".join(lines + ["本日は基準を満たす候補なし", "無理なエントリーは見送ります。"])
    for row in rows:
        f = row["features"]; c = row["comment"]
        lines.extend([
            f"{row['rank']}. {row.get('name') or row['code']}（{row['code']}） {row['score']}点",
            f"テーマ：{' / '.join(row.get('themes') or ['その他'])}",
            f"株価：{_yen(f.get('price'))}  GAP：{_pct(f.get('gap_rate'))}  出来高ペース：{_ratio(f.get('volume_ratio'))}",
            f"理由：{' / '.join(c['reasons'])}", f"戦略：{c['entry_strategy']}",
            f"利確候補：{_yen(c.get('take_profit'))}  損切り候補：{_yen(c.get('stop_loss'))}",
            f"リスク：{' / '.join(c['risks'])}", "",
        ])
    lines.append("※寄り付き後の速報値を含みます。板・PTS等の未取得項目は加点していません。投資判断は自己責任でお願いします。")
    return "\n".join(lines).strip()


def send_ranking(payload: dict[str, Any]) -> bool: return post_message(format_ranking(payload))
def _pct(value: Any) -> str: return "--" if value is None else f"{float(value):+.1%}"
def _ratio(value: Any) -> str: return "--" if value is None else f"{float(value):.1f}倍"
def _yen(value: Any) -> str: return "--" if value is None else f"{float(value):,.0f}円"
