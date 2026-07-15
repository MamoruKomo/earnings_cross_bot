# Earnings Cross Manager

日本株の決算跨ぎ判断と日々の市場運用を、macOSネイティブアプリで一元管理するプロジェクトです。市場朝刊、ウォッチリスト、ファンダランキングを統合しています。

GitHub Pagesは使用しません。GitHub Actionsがデータを更新し、`data/manager_snapshot.json` をSwiftUIアプリがローカルから読み込みます。

## 管理できるもの

- 当日の決算跨ぎ候補とSlack通知状態
- 翌営業日の結果検証、勝率、リターン、自己学習
- 寄り前のMarket Morning Briefと過去30件
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
python3 -m src.main_daytrade rank --no-slack
python3 -m src.main_daytrade evaluate
```

## 振り返りと改善のタイミング

- 平日15:45 JST: 前営業日の推奨を翌営業日の始値・終値で評価します。始値または終値が+3%以上なら正答、両方が-3%以下なら誤答、それ以外は中立です。
- 金曜18:00 JST: その週の成績、成功・失敗パターン、スコア帯別正答率をレビューします。
- 同じ金曜18:00 JST: 30件を学習用、直近10件を未見の検証用として時系列分割します。未見10件で正答率と平均リターンが悪化しない場合だけ補正を採用します。
- 40件未満: 自動補正は行わず観測だけに留めます。正答率には95%信頼区間を併記し、少数サンプルの上振れを区別します。

ネイティブアプリの「検証」画面では、全期間と未見データの正答率、95%信頼下限、スコア帯別精度を確認できます。

## デイトレ銘柄選定AI

- 平日8:50 JST: Yahooの日足・5分足、TDnet蓄積データ、市場朝刊、PR TIMES・日経・Kabutanの公開見出しから最大10銘柄をランキングし、Slackへ投稿します。
- 平日15:50 JST: 選定時刻より後の5分足だけを使い、当日高値・安値・終値、最大上昇率・最大下落率、+3%到達、-2%到達を記録します。
- 指標: 前日比、GAP、出来高ペース、売買代金、時価総額、VWAP、ATR、年率ボラティリティ、MA5/20、MACD、RSI、出来高急増、20日高値・ボックスブレイク。
- 採点: 流動性20、ボラティリティ15、ニュース20、テーマ10、テクニカル20、板5、リスクリワード10の100点満点です。
- 学習: 30件を学習、直近10件を未見検証に使い、的中率を落とさず候補カバレッジ50%以上を維持する補正だけ採用します。

信用残、空売り比率、PTS、板情報は取得できた場合だけ利用する拡張項目です。現在の公開データ経路で未取得の場合は加点せず、Slackとアプリで板確認を促します。

市場情報:

```bash
cd market_intelligence
python3 scripts/morning_brief.py --manager-only
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

- 平日 08:05: ファンダ更新
- 平日 08:20: 市場朝刊
- 平日 08:30: 決算跨ぎ候補
- 平日 09:30 / 16:00: ウォッチリスト
- 平日 15:45: 結果評価
- 金曜 18:00: 週次レビュー

手動実行では `morning`、`evaluate`、`weekly`、`learn`、`slack-test`、`market-brief`、`watchlist-open`、`watchlist-close`、`fundamentals`、`refresh-manager`、`build-native` を選択できます。

各runは共通のcheckout・Python setup・依存キャッシュを使い、最後にManagerスナップショットを再生成してデータ変更を1回だけcommitします。

## データ保存

- `data/earnings_cross_bot.db`: 推奨、評価、学習、通知履歴
- `data/manager_snapshot.json`: SwiftUI向け統合スナップショット
- `market_intelligence/docs/data/`: 朝刊、ウォッチ、ファンダの原データ

認証情報は `.env` またはGitHub Actions Secretsに置き、リポジトリへcommitしません。

## 注意

本システムは投資判断の検証支援用です。自動売買は行わず、利益や株価反応を保証しません。
