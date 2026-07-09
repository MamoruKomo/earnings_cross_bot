# 日本株 決算跨ぎ推奨AI

毎営業日の朝 8:30 JST に、その日に決算発表予定の日本株から決算跨ぎ候補を 0〜3 銘柄選び、Slack Incoming Webhook に投稿する MVP です。自動売買は行わず、投資判断の補助と検証ログ作成に目的を絞っています。

## できること

- J-Quants API を第一候補にした決算予定、株価、財務データ取得
- J-Quants が使えない場合の手動 CSV / モックデータ fallback
- ルールベースの 100 点スコアリング
- LLM による JSON 形式の理由生成
- Slack Incoming Webhook 投稿
- 翌営業日 15:45 以降の推奨結果検証
- SQLite への特徴量、推奨、結果、反省ログ保存
- 週次レビューと `config/rules_suggestion.yaml` への改善案保存

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` に必要な値を設定します。

```dotenv
JQUANTS_EMAIL=
JQUANTS_PASSWORD=
JQUANTS_REFRESH_TOKEN=
OPENAI_API_KEY=
SLACK_WEBHOOK_URL=
TIMEZONE=Asia/Tokyo
```

J-Quants は `JQUANTS_REFRESH_TOKEN` があればそれを優先し、なければメールアドレスとパスワードから refresh token を取得しにいきます。外部 API キーがない環境では `data/earnings_calendar_manual.csv` とモックデータを使って動作します。

## 手動CSV形式

`data/earnings_calendar_manual.csv`

```csv
date,code,name,announcement_time,fiscal_quarter,source
2026-07-09,7203,トヨタ自動車,15:00,Q1,mock
```

発表時刻が `15:00` 未満の場中決算は MVP では除外します。`不明` や空欄は対象に残しますが、時刻リスクとして減点します。

## 実行方法

朝の推奨:

```bash
python -m src.main_morning
```

翌営業日の検証:

```bash
python -m src.main_evaluate
```

週次レビュー:

```bash
python -m src.main_weekly_review
```

日付を指定する場合:

```bash
python -m src.main_morning --date 2026-07-09
python -m src.main_evaluate --date 2026-07-10
python -m src.main_weekly_review --date 2026-07-10
```

## Slack連携

Slack Incoming Webhook URL を `.env` の `SLACK_WEBHOOK_URL` に設定してください。未設定の場合は Slack 送信せず、投稿予定の本文を標準出力に表示します。

## GitHub Actions

`.github/workflows/earnings-cross-bot.yml` に以下を設定しています。

- 平日 08:30 JST: 朝の推奨
- 平日 15:45 JST: 翌営業日検証
- 金曜 18:00 JST: 週次レビュー

日本の祝日や休場日は `src/trading_calendar.py` で判定し、スクリプト側で skip します。

## 保存先

SQLite DB:

```text
data/earnings_cross_bot.db
```

主なテーブル:

- `earnings_events`
- `daily_prices`
- `financial_features`
- `earnings_reactions`
- `recommendations`
- `outcomes`
- `lessons`
- `weekly_reviews`
- `llm_runs`

## 注意事項

これは投資助言ではなく、検証用の意思決定支援ツールです。推奨結果はルールベースのスコアと LLM による説明生成であり、利益や株価反応を保証するものではありません。実運用前にデータ品質、J-Quants プランの取得可能範囲、Slack 投稿先、評価閾値を確認してください。

