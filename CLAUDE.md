# CLAUDE.md

このファイルは、Claude Code (claude.ai/code) がこのリポジトリで作業する際のガイダンスを提供します。

## アプリの起動方法

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# メインアプリの起動（ポート8888）
python3 app.py

# その他のバリアント
python3 memo_edit_app.py      # 単一メモ編集アプリ
python3 memo_login.py         # ログイン機能付きメモアプリ（MEMO_PASSWORD 環境変数でパスワード設定）
```

初回起動時にSQLiteデータベースが自動で作成されます。

## アーキテクチャ

教材用Flaskコードベース（書籍: book-webservice-sample）。同じメモアプリを複数の実装で比較し、Webセキュリティの概念を学ぶための構成になっています。

| ファイル | 説明 |
|----------|------|
| `app.py` | Jinja2テンプレートを使ったメインのマルチメモアプリ |
| `memo_edit_app.py` | `werkzeug.utils.escape()` で明示的にXSS対策した単一メモアプリ |
| `memo_login.py` | セッションベースの認証付きマルチメモアプリ。パスワードは `MEMO_PASSWORD` 環境変数で設定 |
| `xss_ng_memo_edit_app.py` | **意図的に脆弱な実装** — XSSの教材用デモ。本番環境では使用しないこと |
| `index.cgi` | 共有ホスティング向けCGIラッパー（シバンとサーバー名の変更が必要） |

### データモデル

全バリアントともSQLAlchemy + SQLiteを使用。`app.py` と `memo_login.py` は `memo.sqlite`、単一メモ系は `memo_edit.sqlite` を使用します。モデルは `MemoItem`（フィールド: `id`, `title`, `body`）のみです。

### テンプレート

`templates/` 内のJinja2テンプレートは `base.html`（BulmaCSS使用）を継承します。テンプレートを使うのは `app.py` のみで、他のバリアントはPython内でHTMLを直接生成しています。

## テスト

修正を行った際は必ず単体テストと結合テストを実施すること。

```bash
# テストの実行
pip install pytest
pytest tests/

# 特定ファイルのみ実行
pytest tests/test_app.py
```

### テストコードの保存ルール

- テストコードは `tests/` フォルダに保存する
- ファイル名はテスト対象がわかるように命名する（例: `test_app.py`, `test_memo_login.py`）
- 単体テスト（関数・モデル単位）と結合テスト（画面遷移・HTTPリクエスト単位）の両方を作成する

---

### セキュリティについて

- `xss_ng_memo_edit_app.py` は比較・学習目的で意図的にXSS脆弱性を含んでいます
- `app.py` はJinja2の自動エスケープに依存、`memo_edit_app.py` と `memo_login.py` は明示的に `escape()` を使用
- コメントは日本語で記述されており、番号付きコメント（※1、※2）は教材の該当箇所を参照しています
