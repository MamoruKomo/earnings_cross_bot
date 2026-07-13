# Earnings Cross Manager

日本株の決算跨ぎ判断と日々の市場運用を、macOSネイティブアプリで一元管理するプロジェクトです。旧 `market-morning-brief` の朝刊、適時開示、ウォッチリスト、ファンダランキングを統合しています。

GitHub Pagesは使用しません。GitHub Actionsがデータを更新し、`data/manager_snapshot.json` をSwiftUIアプリがローカルから読み込みます。

## 管理できるもの

- 当日の決算跨ぎ候補とSlack通知状態
- 翌営業日の結果検証、勝率、リターン、自己学習
- 寄り前のMarket Morning Briefと過去30件
- TDnet適時開示の検索、タグ、公式PDF
- ウォッチリストの寄り・引け価格、前日比、出来高
- 業績成長率、信用需給、ファンダランキング

## 構成

```text
src/                    決算跨ぎ、評価、学習、Managerデータ生成
market_intelligence/    旧market-morning-briefから統合した処理とデータ
data/                   SQLiteとManagerスナップショット
native/                 Earnings Cross Manager（SwiftUI）
.github/workflows/      1つに統合した定期・手動オペレーション
```

`market_intelligence/docs/data/` は旧システムとのデータ互換レイヤーです。HTML公開には使わず、Python処理の保存先としてのみ利用します。

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

主な環境変数:

```dotenv
JQUANTS_EMAIL=
JQUANTS_PASSWORD=
JQUANTS_REFRESH_TOKEN=
OPENAI_API_KEY=
SLACK_WEBHOOK_URL=
EDINETDB_API_KEY=
TIMEZONE=Asia/Tokyo
```

## ローカル実行

```bash
python3 -m src.main_morning
python3 -m src.main_evaluate
python3 -m src.main_weekly_review
python3 -m src.main_learn
python3 -m src.main_dashboard
```

市場情報:

```bash
cd market_intelligence
python3 scripts/morning_brief.py --manager-only
python3 scripts/tdnet_alert.py
python3 scripts/watchlist_snapshot.py --phase close
python3 scripts/fundamentals_edinetdb_rankings.py
```

## macOSアプリ

macOS 14以降:

```bash
./scripts/build_native_app.sh
open build/EarningsCrossManager.app
```

アプリはrepo内の `data/manager_snapshot.json` を読みます。「データを同期」すると `git pull --rebase origin main` を実行します。各更新ボタンはGitHub Actionsの対応ジョブを起動し、完了後に同期します。

## GitHub Actions

`.github/workflows/earnings-cross-bot.yml` が全処理の共通入口です。

- 15分ごと: TDnet適時開示
- 平日 08:05: ファンダ更新
- 平日 08:20: 市場朝刊
- 平日 08:30: 決算跨ぎ候補
- 平日 09:30 / 16:00: ウォッチリスト
- 平日 15:45: 結果評価
- 金曜 18:00: 週次レビュー

手動実行では `morning`、`evaluate`、`weekly`、`learn`、`slack-test`、`market-brief`、`tdnet`、`watchlist-open`、`watchlist-close`、`fundamentals`、`refresh-manager` を選択できます。

各runは共通のcheckout・Python setup・依存キャッシュを使い、最後にManagerスナップショットを再生成してデータ変更を1回だけcommitします。

## データ保存

- `data/earnings_cross_bot.db`: 推奨、評価、学習、通知履歴
- `data/manager_snapshot.json`: SwiftUI向け統合スナップショット
- `market_intelligence/docs/data/`: 朝刊、適時開示、ウォッチ、ファンダの原データ

認証情報は `.env` またはGitHub Actions Secretsに置き、リポジトリへcommitしません。

## 注意

本システムは投資判断の検証支援用です。自動売買は行わず、利益や株価反応を保証しません。
