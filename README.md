# industry-topics-tool

GemMedの最新記事3件を取得し、AIで要約したうえで **静的サイト `site/`** に日次 HTML を蓄積するツール。GitHub Actions で `site/` をコミットし Surge にデプロイしたあと、Slack に短い通知を送ります。

## ディレクトリ構成

```
industry-topics-tool/
  src/
    fetch/           # GemMed スクレイプ
    ai/              # 構造化（1記事1回の API）
    render/          # Jinja2 テンプレート → site/
    notify/          # Slack（post_slack は CI 用）
  site/              # 生成 HTML（Git 管理。日付フォルダが増える）
  data/              # 中間 JSON（.gitignore）
  output/            # 旧ローカル検証用（.gitignore、未使用でも可）
  requirements.txt
  README.md
```

## セットアップ

```bash
cd industry-topics-tool
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
Copy-Item .env.example .env   # PowerShell
# .env に ANTHROPIC_API_KEY を設定。Slack まで試すなら SLACK_WEBHOOK_URL と PUBLIC_URL も。
```

## ローカル実行

```powershell
# 取得 → AI → site/{YYYY-MM-DD}/index.html + site/index.html → Slack（PUBLIC_URL があるときのみ送信）
python src/run_daily.py

python src/run_daily.py --date 20260411
python src/run_daily.py --skip-fetch
python src/run_daily.py --skip-fetch --skip-analyze
# CI と同じく Slack を後回しにする
python src/run_daily.py --skip-notify
```

個別ステップは従来どおり `src/ai/analyzer.py` や `src/render/render_html.py` でも実行可能です。

### HTML のみ確認（ダミーデータ）

```bash
python src/render/render_html.py
```

`site/{今日の日付}/index.html` と `site/index.html` が生成されます。

## データフロー

```
GemMed
  → fetch → data/raw_articles_YYYYMMDD.json
  → analyzer → data/structured_YYYYMMDD.json
  → render → site/YYYY-MM-DD/index.html と site/index.html
  → slack（ローカル） / post_slack.py（CI・Surge 後）
```

## GitHub Actions（`daily.yml`）

このリポジトリがルートの場合、[.github/workflows/daily.yml](.github/workflows/daily.yml) が次の順で動きます。

モノレポ（親リポジトリ `commit-report-tool`）で動かす場合は、親側の [.github/workflows/new-daily.yml](../../.github/workflows/new-daily.yml) を参照してください。

1. `python src/run_daily.py --skip-notify`（`site/` 生成）
2. `industry-topics-tool/site` を commit & push
3. `npx surge ./industry-topics-tool/site <ドメイン> --token …` でデプロイ
4. **`python src/notify/post_slack.py`** で Slack（**Surge 成功後**のみ送信）

### Secrets（例）

| Secret | 用途 |
|--------|------|
| `ANTHROPIC_API_KEY` | AI |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook |
| `PUBLIC_URL` | 公開 URL のベース（末尾スラッシュなし）。**Actions 上では必須** |
| `SURGE_TOKEN` | Surge [トークン](https://surge.sh/help/integrating-with-ci) |
| `SURGE_DOMAIN` | 例: `medical-topics-ryo.surge.sh` |

ブランチ保護で `github-actions[bot]` の push が拒否される場合は、ルールの例外設定が必要です。

## 環境変数

| 変数名 | ローカル | GitHub Actions |
|--------|----------|----------------|
| `ANTHROPIC_API_KEY` | 必須（AI 利用時） | 必須 |
| `SLACK_WEBHOOK_URL` | 任意 | `post_slack` で必須 |
| `PUBLIC_URL` | 任意（未設定なら Slack はスキップし警告） | **必須** |

## 将来メモ（保存期間）

現状は `site/` を Git にそのまま蓄積で問題ありません。日次 HTML が増えリポジトリが重くなった場合に備え、**直近 180 日や 365 日に保存期間を制限する**などの整理余地はあります（現時点では未実装）。

## structured JSON の形（概要）

各記事は API 1回で次のようなフィールドをまとめて返します（詳細は `src/ai/analyzer.py`）。

- HTML 用: `points`（2件）, `implication`, `tags`（3件）
- Slack 用: `slack_title`, `slack_note`
