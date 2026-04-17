# industry-topics-tool

GemMedの最新記事3件を取得し、HTMLダッシュボードをローカルに生成するツール。

## ディレクトリ構成

```
industry-topics-tool/
  src/
    fetch/
      list_pages.py      # GemMedトップからURL取得
      article_pages.py   # 記事本文取得
    render/
      template.html      # Jinja2 HTMLテンプレート
      render_html.py     # テンプレートにデータ差し込み → HTML出力
    main.py              # 記事取得 → data/raw_articles_YYYYMMDD.json
  data/                  # 中間JSONファイル（.gitignore対象）
  output/                # 生成HTML（.gitignore対象）
  requirements.txt
  README.md
```

## セットアップ

```bash
cd industry-topics-tool

# 仮想環境を作成・有効化（推奨）
python -m venv .venv
# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

# 依存ライブラリをインストール
pip install -r requirements.txt
```

## ローカル実行手順

### Step A: 記事データを取得する

```bash
python src/main.py
```

実行後、`data/raw_articles_YYYYMMDD.json` が生成される。

### Step B: HTMLをダミーデータで確認する

```bash
python src/render/render_html.py
```

`output/index.html` が生成される。ブラウザで開いて表示を確認する。

### Step C: AIで記事を構造化する

事前に `.env` ファイルを作成してAPIキーを設定してください。

```powershell
# .env.example をコピーして .env を作成
Copy-Item .env.example .env
# .env を開いて ANTHROPIC_API_KEY を設定
```

```powershell
python src/ai/analyzer.py
```

`data/structured_YYYYMMDD.json` が生成される。

### Step D: 実データでHTMLを生成する

```powershell
python src/render/render_html.py --data data/structured_YYYYMMDD.json
```

### 出力ファイルを指定する場合

```bash
python src/render/render_html.py --out output/report_20260411.html
```

## 現在の実装状況（PoC）

- [x] GemMedスクレイプ（URL取得・本文取得）
- [x] raw JSON 保存
- [x] HTMLテンプレート（Tailwind CDN、3段構成）
- [x] ダミーデータでのHTML生成
- [ ] AI要約・構造化（次のステップ）
- [ ] Slack通知
- [ ] GitHub Actions

### 全自動実行（推奨）

```powershell
# 取得 → AI要約 → HTML生成 → Slack通知 を一括実行
python src/run_daily.py

# 日付指定
python src/run_daily.py --date 20260411

# 取得をスキップ（既存 raw JSON を使う）
python src/run_daily.py --skip-fetch

# AI要約もスキップ（既存 structured JSON を使う）
python src/run_daily.py --skip-fetch --skip-analyze
```

## データフロー

```
GemMedトップ
  → src/fetch/list_pages.py    → URL × 3
  → src/fetch/article_pages.py → data/raw_articles_YYYYMMDD.json
  → src/ai/analyzer.py         → data/structured_YYYYMMDD.json
  → src/render/render_html.py  → output/index.html
  → src/notify/slack.py        → Slack 通知
```

## 環境変数一覧

| 変数名 | 必須 | 説明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 必須 | AI要約に使用 |
| `SLACK_WEBHOOK_URL` | 任意 | 未設定時は通知スキップ |
| `PUBLIC_URL` | 任意 | 設定時はSlackにURLを通知。未設定時はローカルパス |
