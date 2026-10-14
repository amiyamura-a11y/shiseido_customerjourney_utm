# ULTIMUNE | Journey Analytics

資生堂アルティミューンの個票CSV（1行1人・行動01〜25）から、カスタマージャーニー／Golden Path を**都度再計算**して表示する業務用分析ダッシュボードです。Media Flow メジャメント画面を参考にした白基調のUIで、AI Cockpit・チャットUIは搭載していません。

- Frontend: Next.js 15 / React 19 / TypeScript / Tailwind CSS v4 / React Flow (@xyflow/react) / Recharts / Zustand
- Backend: Python 3.11+ / FastAPI / pandas / pyarrow (Parquet) / openpyxl
- 外部LLM APIは不要。すべてローカルで動作します。

## 1. ディレクトリ構成

```
backend/            FastAPI + 集計エンジン（app/）、pytest（tests/）
frontend/           Next.js アプリ（src/app 配下に 6 ページ）
data/raw/           入力ファイルを置く場所（git管理外）
data/processed/     正規化済み Parquet キャッシュ（自動生成・git管理外）
data/uploads/       画面からアップロードしたファイル（git管理外）
docs/               入力検査レポート・参照資料
scripts/dev.sh      バックエンド＋フロントエンド同時起動
```

## 2. 入力ファイル

`data/raw/` に以下を置きます（ファイル名は部分一致で自動検出。列・シートはコードが検査します）。

| 役割 | 検出パターン | 用途 |
|---|---|---|
| 個票CSV（正本） | `*パス分析*.csv` | 年代／結果／タイプ分類／開始期／日数／行動数／行動01〜25 |
| パス分析結果Excel | `*パス分析結果*.xlsx` | `マスタ`（個別変数→分析用カテゴリ）、既存集計の照合 |
| 追加集計Excel | `*追加集計*.xlsx` | 年代別出現率・悩み系KW起点パスの照合 |
| 行動変数加工Excel | `*行動変数加工*.xlsx` | 加工定義とマスタの不一致一覧（マスタは上書きしない） |

CSV は UTF-8 BOM／UTF-8／CP932 を自動判定します。`全パターン` シートは CSV と同一内容のため読み込みません（二重計上防止）。

## 3. 起動方法

```bash
# 依存関係
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm install

# 起動（2ターミナル、または ./scripts/dev.sh）
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000 --reload
cd frontend && npm run dev          # http://localhost:3000
```

フロントは `/api/*` をバックエンド（既定 `http://127.0.0.1:8000`）へリライトします。別ホストの場合は `API_ORIGIN` 環境変数で指定してください。初回起動時に CSV を正規化して `data/processed/` に Parquet を保存します（約5秒）。

## 4. テスト

```bash
cd backend && source .venv/bin/activate && python -m pytest -q
cd frontend && npx tsc --noEmit && npx eslint src && npm run build
```

pytest は合成データによる単体テスト（行動順序・欠損・繰り返し保持、D−n解析とカテゴリ変換、ステップ別ノード人数／率、エッジ遷移人数／率、3〜5接点完全パス、同一人物の重複防止、年代／購入有無／期間フィルタの分母、非購入者に購入Outcomeを付与しない、先頭／末尾ステップの違い）と、実データがある場合のExcel照合テスト（悩み検索起点2接点、パス優先度、個別変数出現率）を含みます。

## 5. ページ

| # | ページ | 内容 |
|---|---|---|
| 01 | データ概観 | 母数KPI、行動数／期間分布、タイプ分類、行動カテゴリ一覧（購入者／非購入者差）、データ品質 |
| 02 | Golden Path | STEP1→…→Outcome。ノード面積＝経験率、エッジ幅＝遷移人数、ラベル＝条件付き遷移率。先頭／末尾／任意起点／全25ステップ。クリックで完全パスの人数・率を再計算 |
| 03 | パス比較 | プリセット（購入者vs非購入者／年代／短期vs長期）＋任意A/B。ノード位置・スケールを揃えた左右比較、差pt・倍率、差分ランキング |
| 04 | 時系列分析 | D−30〜D−0 ヒートマップ、日別推移、時期別ランキング、観測期間別比較 |
| 05 | 起点行動分析 | 起点→2番目→3番目…（2〜10）。初回／最終／全出現、直後／指定カテゴリ／指定日数内。追加集計Excelとの照合 |
| 06 | パス詳細探索 | 起点・終点・経由・ステップ数・閾値で検索。匿名の実行動例、セグメント比較、Golden Pathへのハイライト |

## 6. 集計定義（要点）

- 行動単体経験率＝1回以上経験したユニーク人数÷フィルタ対象者数 n
- ステップnのノード経験率＝ステップnで当該行動を経験した人数÷n、ステップn到達者内構成比＝÷ステップn到達者数
- A→B遷移率＝AからBへ遷移したユニーク人数÷Aの該当ステップ到達者数
- 完全パス経験率＝指定パスを実際に満たすユニーク人数÷n（**率の積は使わない**）
- 連続パス（隣接遷移）と順序保持パス（間に他行動を許容、初回出現ベース）は別モード。順序保持の全列挙は3ステップまで
- 購入Outcomeは最終観測行動の後にのみ接続。表示範囲後にも行動がある人は「後続行動あり」。非購入者の終端は「非購入／観測終了」
- 行動発生時期フィルタ適用後の隣接は「期間内抽出後の隣接」として明示
- 大分類＝変数名の先頭語（検索／外部サイト／自社サイト／競合検索／LISA）
- 非購入者の基準日は購入日ではないため「基準日」「観測期間」と表記
- 既存Excelの推計UTM購買率は別指標（事前購買率を逆算した推計前提を注記）

## 7. API

`POST /api/overview`, `POST /api/paths/graph`, `POST /api/paths/compare`, `POST /api/paths/entry`, `GET /api/paths/entry/options`, `POST /api/paths/search`, `POST /api/paths/detail`, `POST /api/timeline`, `GET /api/labels`, `GET /api/dictionary`, `GET /api/validation`, `POST /api/upload`, `POST /api/reload`, `POST /api/cache/clear`, `GET /api/meta`, `GET /api/health`。OpenAPI は `http://127.0.0.1:8000/docs`。

レスポンスには対象者数 n、各指標の分母、人数、率、適用したフィルタ／パス定義、打ち切り情報（censoring）、注記（notes）を含みます。

## 8. Webデプロイ（GitHub からの自動デプロイ）

GitHub Pages は静的サイト専用のため、本アプリ（Python バックエンド必須）は **Docker イメージ** としてデプロイします。リポジトリ直下の `Dockerfile` は Next.js を静的書き出し（`NEXT_OUTPUT=export`）し、FastAPI が API と画面を同一オリジンで配信します（ポート `PORT`、既定 8000）。

### 8.1 認証
公開URLに置く場合は必ず環境変数 `APP_USER` / `APP_PASSWORD` を設定してください。設定すると全ページ・全APIが HTTP Basic 認証で保護されます（`/api/health` のみ除外）。

### 8.2 データの扱い（重要）
**このリポジトリは public です。** `data/raw/` は `.gitignore` 済みで、個票CSV・Excel はリポジトリにも GitHub Actions で作るイメージにも含まれません。デプロイ後に画面07「データ・変数定義」の **CSV/Excelアップロード** から4ファイルを投入してください。アップロードした CSV は `data/raw` が空のとき同ディレクトリに保存されるため、永続ディスクをマウントしていれば再起動後も保持されます。

### 8.3 Render（推奨・最短）
1. Render で New → Blueprint → このリポジトリを選択（`render.yaml` を自動検出）。
2. Environment に `APP_USER` / `APP_PASSWORD` を設定。永続化したい場合は Disk を `/app/data` にマウント。
3. デプロイ完了後、発行URLを開き、画面07からデータをアップロード。以後 `git push` のたびに自動再デプロイ。

### 8.4 GitHub Container Registry（任意のホストで）
`.github/workflows/docker-image.yml` が push ごとに `ghcr.io/<owner>/shiseido_customerjourney_utm:<branch>` を作成します。Cloud Run／Azure Container Apps／Fly.io 等でこのイメージを指定し、`PORT`（Cloud Run は 8080）と認証用環境変数を設定、`/app/data` にボリュームをマウントしてください。

```bash
# Cloud Run の例
gcloud run deploy ultimune-journey --image ghcr.io/amiyamura-a11y/shiseido_customerjourney_utm:claude-epic-keller-tbdwep \
  --region asia-northeast1 --port 8080 --memory 2Gi --set-env-vars APP_USER=...,APP_PASSWORD=...
```

### 8.5 ローカルで Docker 実行
```bash
docker build -t utm-journey .
docker run -p 8000:8000 -e APP_USER=demo -e APP_PASSWORD=secret -v "$PWD/data:/app/data" utm-journey
```

### 8.6 静的HTML版（バックエンド不要）
`backend/scripts/export_static_html.py` は、正規化済みの個票を埋め込んだ **単一HTMLファイル**（既定 `site/index.html`、約2.5MB）を書き出します。すべての集計はブラウザ内で再計算され、バックエンド無しで 6 ページが動作します（アップロード・再読み込みのみ非対応。Excel照合は生成時の結果を埋め込み）。

```bash
cd backend && source .venv/bin/activate && python scripts/export_static_html.py --out ../site/index.html
```

**注意**: このHTMLには匿名化済みとはいえ個票の行動系列がそのまま埋め込まれます。GitHub Pages は常に公開ページで認証を付けられないため、公開する場合はその前提を確認してください（`site/` は既定で git 管理外）。閲覧制限が必要な場合は 8.3〜8.5 のコンテナ版（Basic認証あり）を使ってください。

## 9. 既知の制約・未解決事項

`docs/data_inspection_report.md` を参照してください。
