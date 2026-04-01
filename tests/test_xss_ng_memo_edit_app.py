"""
xss_ng_memo_edit_app.py のテスト
対象機能: 単一メモの基本動作 + XSS脆弱性の存在確認（教材用）

注意: TestXssVulnerability クラスは「脆弱性が存在すること」を検証するテストです。
      本番アプリにこのような脆弱性があってはいけません。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from xss_ng_memo_edit_app import app, db, MemoItem


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


# ============================================================
# 結合テスト: 基本ルート
# ============================================================

class TestRoutes:

    def test_get_shows_form(self, client):
        """GETでメモ編集フォームが表示されること"""
        res = client.get("/")
        assert res.status_code == 200
        assert "タイトル:".encode() in res.data

    def test_initial_memo_created_on_first_get(self, client):
        """初回GETで初期メモ（id=1）が自動作成されること"""
        client.get("/")
        with app.app_context():
            item = MemoItem.query.get(1)
            assert item is not None
            assert item.title == "無題"

    def test_post_saves_memo(self, client):
        """POSTでメモの内容が保存されること"""
        client.get("/")
        client.post("/", data={"title": "保存テスト", "body": "本文"}, follow_redirects=True)
        with app.app_context():
            item = MemoItem.query.get(1)
            assert item.title == "保存テスト"

    def test_post_redirects_after_save(self, client):
        """保存後にリダイレクトされること"""
        client.get("/")
        res = client.post("/", data={"title": "テスト", "body": ""})
        assert res.status_code == 302

    def test_empty_title_returns_error(self, client):
        """タイトルが空のときエラーメッセージが返ること"""
        client.get("/")
        res = client.post("/", data={"title": "", "body": "本文"})
        assert "タイトルは空にできません".encode() in res.data


# ============================================================
# 結合テスト: XSS脆弱性の確認（教材用 — 脆弱性が存在することを検証）
# ============================================================

class TestXssVulnerability:
    """
    このクラスは「XSSエスケープが行われていないこと」を確認するテストです。
    memo_edit_app.py（セキュア版）と比較するための教材用テストです。
    """

    def test_xss_in_title_is_NOT_escaped(self, client):
        """タイトルのスクリプトタグがエスケープされず、そのまま出力されること（脆弱性）"""
        client.get("/")
        xss = "<script>alert('xss')</script>"
        client.post("/", data={"title": xss, "body": ""})
        res = client.get("/")
        assert b"<script>" in res.data, "XSS脆弱性: タイトルがエスケープされていないこと"

    def test_xss_in_body_is_NOT_escaped(self, client):
        """本文のスクリプトタグがエスケープされず、そのまま出力されること（脆弱性）"""
        client.get("/")
        xss = "<script>alert('xss')</script>"
        client.post("/", data={"title": "テスト", "body": xss})
        res = client.get("/")
        assert b"<script>" in res.data, "XSS脆弱性: 本文がエスケープされていないこと"
