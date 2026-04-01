"""
memo_edit_app.py のテスト
対象機能: 単一メモの表示・保存、バリデーション、XSSエスケープ
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from memo_edit_app import app, db, MemoItem


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app.test_client()
        db.drop_all()


# ============================================================
# 単体テスト: MemoItem モデル
# ============================================================

class TestMemoItemModel:

    def test_create_memo(self, client):
        """メモをDBに保存・取得できること"""
        with app.app_context():
            item = MemoItem(id=1, title="テスト", body="本文")
            db.session.add(item)
            db.session.commit()
            found = MemoItem.query.get(1)
            assert found.title == "テスト"
            assert found.body == "本文"


# ============================================================
# 結合テスト: ルート
# ============================================================

class TestMemoEditRoutes:

    def test_get_shows_form(self, client):
        """GETでメモ編集フォームが表示されること"""
        res = client.get("/")
        assert res.status_code == 200
        assert "タイトル:".encode() in res.data

    def test_initial_memo_created_on_first_get(self, client):
        """初回GETアクセスで初期メモ（id=1）が自動作成されること"""
        client.get("/")
        with app.app_context():
            item = MemoItem.query.get(1)
            assert item is not None
            assert item.title == "無題"

    def test_post_saves_memo(self, client):
        """POSTでメモの内容が保存されること"""
        client.get("/")  # 初期メモ作成
        client.post("/", data={"title": "保存テスト", "body": "本文内容"}, follow_redirects=True)
        with app.app_context():
            item = MemoItem.query.get(1)
            assert item.title == "保存テスト"
            assert item.body == "本文内容"

    def test_post_redirects_to_index(self, client):
        """保存後にトップページへリダイレクトされること"""
        client.get("/")
        res = client.post("/", data={"title": "テスト", "body": ""})
        assert res.status_code == 302

    def test_empty_title_returns_error(self, client):
        """タイトルが空のときエラーメッセージが返ること"""
        client.get("/")
        res = client.post("/", data={"title": "", "body": "本文"})
        assert "タイトルは空にできません".encode() in res.data


# ============================================================
# 結合テスト: XSSエスケープ（セキュアな実装の確認）
# ============================================================

class TestXssEscaping:

    def test_xss_in_title_is_escaped(self, client):
        """タイトルに含まれるスクリプトタグがエスケープされること"""
        client.get("/")
        xss = "<script>alert('xss')</script>"
        client.post("/", data={"title": xss, "body": ""})
        res = client.get("/")
        assert b"<script>" not in res.data
        assert b"&lt;script&gt;" in res.data

    def test_xss_in_body_is_escaped(self, client):
        """本文に含まれるスクリプトタグがエスケープされること"""
        client.get("/")
        xss = "<script>alert('xss')</script>"
        client.post("/", data={"title": "テスト", "body": xss})
        res = client.get("/")
        assert b"<script>" not in res.data
        assert b"&lt;script&gt;" in res.data
