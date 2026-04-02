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

### データモデル（app.py）

`app.py` は SQLAlchemy + SQLite（`instance/memo.sqlite`）を使用。以下のモデルで構成されています。

| モデル | 主なフィールド | 説明 |
|--------|--------------|------|
| `User` | id, username, password_hash | ユーザー |
| `Folder` | id, name, user_id | コルクボード（フォルダ） |
| `MemoItem` | id, title, body, color, tags, pos_x, pos_y, is_public, user_id, folder_id | 付箋 |
| `Vote` | id, memo_id, user_id | いいね（memo_id+user_idにUNIQUE制約） |
| `Comment` | id, memo_id, user_id, body, created_at | コメント |
| `Drawing` | id, folder_id, user_id, type, data, color, width | 描画（pen/arrow） |

その他のバリアント（`memo_login.py` 等）は `memo_edit.sqlite` を使用し、`MemoItem`（id, title, body）のみ。

### テンプレート

`templates/` 内のJinja2テンプレートは `base.html`（BulmaCSS v1.0.2）を継承します。テンプレートを使うのは `app.py` のみで、他のバリアントはPython内でHTMLを直接生成しています。

### 実装済みの主な機能（app.py）

- アカウント登録・ログイン・ログアウト
- フォルダ作成・削除（全ユーザーのフォルダを一覧表示）
- 付箋の作成・編集・削除・ドラッグ&ドロップ移動
- 公開/非公開切り替え（公開=全員が編集可、非公開=作成者のみ）
- Markdownプレビュー（marked.js）、タグ＆カラーラベル（5色）
- 描画ツール（ペン・矢印・消しゴム・Undo）
- いいね（AJAX、1ユーザー1票、トグル式）
- コメント（AJAX投稿・削除）
- 貢献スコアランキング（公開付箋+3、いいね獲得+2、コメント+1）
- ダークモード（localStorageで保持）
- キーワード検索・タグフィルター

### AJAX APIエンドポイント（app.py）

| メソッド | パス | 説明 |
|----------|------|------|
| POST | `/api/memo/<id>/position` | 付箋位置を保存 |
| POST | `/api/memo/<id>/toggle-public` | 公開/非公開切り替え |
| POST | `/api/memo/<id>/vote` | いいねトグル |
| GET | `/api/memo/<id>/comments` | コメント一覧取得 |
| POST | `/api/memo/<id>/comment` | コメント投稿 |
| DELETE | `/api/comment/<id>` | コメント削除 |
| GET | `/api/folder/<id>/ranking` | 貢献スコアランキング取得 |
| POST | `/api/folder/<id>/drawing` | 描画保存 |
| DELETE | `/api/drawing/<id>` | 描画削除 |
| DELETE | `/api/folder/<id>/drawings` | 全描画削除 |

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

## デプロイ

- **GitHub**: https://github.com/tamago-dotcom/memo-app-
- **本番環境**: Render（gunicorn 使用）
- 環境変数 `SECRET_KEY`（必須）、`DATABASE_URL`（未設定時は `sqlite:///memo.sqlite`）

---

### セキュリティについて

- `xss_ng_memo_edit_app.py` は比較・学習目的で意図的にXSS脆弱性を含んでいます
- `app.py` はJinja2の自動エスケープに依存、`memo_edit_app.py` と `memo_login.py` は明示的に `escape()` を使用
- コメントは日本語で記述されており、番号付きコメント（※1、※2）は教材の該当箇所を参照しています
