"""
memo_login.py のテスト
対象機能: セッション認証、メモCRUD、XSSエスケープ
"""
import sys
import os

# MEMO_PASSWORD はモジュールロード時に読み込まれるためインポート前にセット
os.environ.setdefault("MEMO_PASSWORD", "test")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from memo_login import app, db, MemoItem, MEMO_PASSWORD


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app.test_client()
        db.drop_all()


def do_login(client, password=None):
    # モジュールロード時に確定したパスワードを使う（env var の設定順に依存しないため）
    if password is None:
        password = MEMO_PASSWORD
    return client.post("/login", data={"password": password}, follow_redirects=True)


# ============================================================
# 単体テスト: MemoItem モデル
# ============================================================

class TestMemoItemModel:

    def test_create_and_retrieve(self, client):
        """メモをDBに保存・取得できること"""
        with app.app_context():
            item = MemoItem(title="テスト", body="本文")
            db.session.add(item)
            db.session.commit()
            found = MemoItem.query.filter_by(title="テスト").first()
            assert found is not None


# ============================================================
# 結合テスト: 認証
# ============================================================

class TestAuth:

    def test_index_redirects_when_not_logged_in(self, client):
        """未ログイン時はトップページがログイン画面へリダイレクトされること"""
        res = client.get("/")
        assert res.status_code == 302
        assert "/login" in res.headers["Location"]

    def test_memo_redirects_when_not_logged_in(self, client):
        """未ログイン時はメモ画面もリダイレクトされること"""
        res = client.get("/memo/0")
        assert res.status_code == 302
        assert "/login" in res.headers["Location"]

    def test_login_page_is_accessible(self, client):
        """ログインページは未ログインでもアクセスできること"""
        res = client.get("/login")
        assert res.status_code == 200

    def test_login_with_correct_password(self, client):
        """正しいパスワードでログイン後、一覧ページへ遷移すること"""
        res = do_login(client)
        assert res.status_code == 200
        assert "新規作成".encode() in res.data

    def test_login_with_wrong_password(self, client):
        """誤ったパスワードではログインできないこと"""
        res = do_login(client, password="__wrong__password__")
        # ログインページに留まる
        assert "ログイン".encode() in res.data
        assert "新規作成".encode() not in res.data


# ============================================================
# 結合テスト: メモ CRUD
# ============================================================

class TestMemoCRUD:

    def test_new_memo_created_on_get_zero(self, client):
        """id=0 の GET アクセスで新規メモが自動作成されること"""
        do_login(client)
        client.get("/memo/0")
        with app.app_context():
            assert MemoItem.query.count() == 1

    def test_edit_memo(self, client):
        """既存メモを編集して保存できること"""
        do_login(client)
        client.get("/memo/0")
        with app.app_context():
            item_id = MemoItem.query.first().id
        client.post(f"/memo/{item_id}", data={"title": "編集後タイトル", "body": "編集後本文"})
        with app.app_context():
            item = MemoItem.query.get(item_id)
            assert item.title == "編集後タイトル"

    def test_memo_not_found_returns_404(self, client):
        """存在しないメモIDにアクセスすると404が返ること"""
        do_login(client)
        res = client.get("/memo/9999")
        assert res.status_code == 404

    def test_index_shows_memo_titles(self, client):
        """一覧画面にメモのタイトルが表示されること"""
        do_login(client)
        with app.app_context():
            item = MemoItem(title="一覧確認メモ", body="")
            db.session.add(item)
            db.session.commit()
        res = client.get("/")
        assert "一覧確認メモ".encode() in res.data


# ============================================================
# 結合テスト: XSSエスケープ（セキュアな実装の確認）
# ============================================================

class TestXssEscaping:

    def test_xss_in_title_is_escaped_in_list(self, client):
        """一覧画面でタイトルのスクリプトタグがエスケープされること"""
        do_login(client)
        with app.app_context():
            item = MemoItem(title="<script>alert('xss')</script>", body="")
            db.session.add(item)
            db.session.commit()
        res = client.get("/")
        assert b"<script>" not in res.data

    def test_xss_in_title_is_escaped_in_edit(self, client):
        """編集画面でタイトルのスクリプトタグがエスケープされること"""
        do_login(client)
        client.get("/memo/0")
        with app.app_context():
            item = MemoItem.query.first()
            item_id = item.id
        xss = "<script>alert('xss')</script>"
        client.post(f"/memo/{item_id}", data={"title": xss, "body": ""})
        res = client.get(f"/memo/{item_id}")
        assert b"<script>" not in res.data
