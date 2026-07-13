# 日本株 決算跨ぎ推奨AI

毎営業日の朝 8:30 JST に、その日に決算発表予定の日本株から決算跨ぎ候補を 0〜3 銘柄選び、Slack Incoming Webhook に投稿する MVP です。自動売買は行わず、投資判断の補助と検証ログ作成に目的を絞っています。

## できること

- J-Quants API を第一候補にした決算予定、株価、財務データ取得
- J-Quants未設定時はトレーダーズ・ウェブの決算予定/業績とYahoo Financeの日足へ自動切替
- J-Quants が使えない場合の手動 CSV / モックデータ fallback
- ルールベースの 100 点スコアリング
- LLM による JSON 形式の理由生成
- Slack Incoming Webhook 投稿
- 翌営業日 15:45 以降の推奨結果検証
- SQLite への特徴量、推奨、結果、反省ログ保存
- 週次レビューと `config/rules_suggestion.yaml` への改善案保存
- 評価30件から有効になる、変更幅を制限した自己学習プロファイル
- J-Quants / CSVによる信用買残・売残・信用倍率の需給分析
- SwiftUI製macOSネイティブ管理アプリ

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
JQUANTS_PRO_ACCESS_TOKEN=
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

精度ダッシュボード生成:

```bash
python -m src.main_dashboard
python -m src.main_supply_demand
```

日付を指定する場合:

```bash
python -m src.main_morning --date 2026-07-09
python -m src.main_evaluate --date 2026-07-10
python -m src.main_weekly_review --date 2026-07-10
python -m src.main_dashboard
```

## macOSネイティブ管理アプリ

macOS 14以降で、次のコマンドからアプリをビルドできます。

```bash
chmod +x scripts/build_native_app.sh
./scripts/build_native_app.sh
open build/EarningsCrossManager.app
```

アプリでは、起動直後に今日の候補を確認でき、精度サマリー、累積リターン、推奨履歴、銘柄別成績、未評価候補も表示します。候補生成、翌日評価、週次レビュー、学習、SlackテストはすべてGitHub Actionsで実行され、完了後に最新データを自動同期します。

「ファンダ・需給」画面では売上/営業利益成長率と、信用買残・売残・信用倍率・買残前週比を比較できます。J-Quantsで信用残高を取得できない契約では `data/margin_interest_manual.csv` を利用します。

自己学習は評価済み30件未満では重みを変更しません。30件以降、各特徴量の成績差に基づく補正を `data/learning_profile.json` に保存し、1回の変更幅を最大±10%に制限します。元の `config/rules.yaml` は保持されます。

認証情報は従来どおりリポジトリ直下の `.env` を使います。アプリ自体には秘密情報を保存しません。

## ブラウザ版ダッシュボード

`docs/dashboard/index.html` をブラウザで開くと、以下を確認できます。

- 勝率、負けない率、平均翌日始値/終値リターン
- win / neutral / lose の内訳
- 累積翌日終値リターン
- 週次推移
- 銘柄別成績
- 最近の検証結果
- 未検証の推奨

データは `data/earnings_cross_bot.db` から `docs/dashboard/data/dashboard.json` と `docs/dashboard/data/dashboard-data.js` に出力します。GitHub Pages を使う場合は、Pages の公開元を `main` branch の `/docs` に設定してください。

## Slack連携

Slack Incoming Webhook URL を `.env` の `SLACK_WEBHOOK_URL` に設定してください。未設定の場合は Slack 送信せず、投稿予定の本文を標準出力に表示します。

接続テスト:

```bash
python -m src.main_slack_test
```

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
