"""
app.py のテスト
対象機能: アカウント登録、認証、フォルダCRUD、付箋CRUD、公開/非公開切り替え、
         タグ&カラー、いいね、コメント、貢献スコアランキング、描画、ユーザー分離
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app import app, db, User, Folder, MemoItem, Vote, Comment, Drawing


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app.test_client()
        db.drop_all()


def do_register(client, username="testuser", password="testpass"):
    return client.post("/register", data={"username": username, "password": password}, follow_redirects=True)

def do_login(client, username="testuser", password="testpass"):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)

def register_and_login(client, username="testuser", password="testpass"):
    do_register(client, username, password)
    return do_login(client, username, password)

def create_folder(client, name="テストフォルダ"):
    return client.post("/folder/new", data={"name": name}, follow_redirects=True)

def create_memo(client, folder_id, title="テスト付箋", body="本文"):
    return client.post("/memo/new", data={"folder_id": folder_id, "title": title, "body": body}, follow_redirects=True)


# ============================================================
# 単体テスト: モデル
# ============================================================

class TestModels:

    def test_create_user(self, client):
        """ユーザーをDBに保存・取得できること"""
        from werkzeug.security import generate_password_hash
        with app.app_context():
            user = User(username="alice", password_hash=generate_password_hash("pass"))
            db.session.add(user)
            db.session.commit()
            assert User.query.filter_by(username="alice").first() is not None

    def test_username_is_unique(self, client):
        """同じユーザー名は重複登録できないこと"""
        from werkzeug.security import generate_password_hash
        from sqlalchemy.exc import IntegrityError
        with app.app_context():
            db.session.add(User(username="dup", password_hash=generate_password_hash("p")))
            db.session.commit()
            db.session.add(User(username="dup", password_hash=generate_password_hash("p")))
            with pytest.raises(IntegrityError):
                db.session.commit()

    def test_create_folder(self, client):
        """フォルダをDBに保存・取得できること"""
        from werkzeug.security import generate_password_hash
        with app.app_context():
            user = User(username="u", password_hash=generate_password_hash("p"))
            db.session.add(user)
            db.session.commit()
            folder = Folder(name="企画案", user_id=user.id)
            db.session.add(folder)
            db.session.commit()
            assert Folder.query.filter_by(name="企画案").first() is not None

    def test_delete_folder_cascades_memos(self, client):
        """フォルダ削除で中の付箋も削除されること"""
        from werkzeug.security import generate_password_hash
        with app.app_context():
            user = User(username="u", password_hash=generate_password_hash("p"))
            db.session.add(user)
            db.session.commit()
            folder = Folder(name="f", user_id=user.id)
            db.session.add(folder)
            db.session.commit()
            memo = MemoItem(title="m", body="", user_id=user.id, folder_id=folder.id)
            db.session.add(memo)
            db.session.commit()
            memo_id = memo.id
            db.session.delete(folder)
            db.session.commit()
            assert MemoItem.query.get(memo_id) is None

    def test_memo_default_position(self, client):
        """付箋の初期座標が設定されること"""
        from werkzeug.security import generate_password_hash
        with app.app_context():
            user = User(username="u", password_hash=generate_password_hash("p"))
            db.session.add(user)
            db.session.commit()
            folder = Folder(name="f", user_id=user.id)
            db.session.add(folder)
            db.session.commit()
            memo = MemoItem(title="m", body="", user_id=user.id, folder_id=folder.id)
            db.session.add(memo)
            db.session.commit()
            assert memo.pos_x == 40
            assert memo.pos_y == 40


# ============================================================
# 結合テスト: アカウント登録
# ============================================================

class TestRegister:

    def test_register_page_accessible(self, client):
        res = client.get("/register")
        assert res.status_code == 200

    def test_register_success(self, client):
        res = do_register(client)
        assert "アカウントを登録しました".encode() in res.data

    def test_register_saves_user(self, client):
        do_register(client, username="newuser")
        with app.app_context():
            assert User.query.filter_by(username="newuser").first() is not None

    def test_register_password_hashed(self, client):
        do_register(client, username="hashuser", password="mypassword")
        with app.app_context():
            user = User.query.filter_by(username="hashuser").first()
            assert user.password_hash != "mypassword"

    def test_register_duplicate_username(self, client):
        do_register(client, username="dup")
        res = do_register(client, username="dup")
        assert "すでに使用されています".encode() in res.data

    def test_register_empty_username(self, client):
        res = client.post("/register", data={"username": "", "password": "pass"}, follow_redirects=True)
        assert "ログインIDを入力してください".encode() in res.data

    def test_register_empty_password(self, client):
        res = client.post("/register", data={"username": "user", "password": ""}, follow_redirects=True)
        assert "パスワードを入力してください".encode() in res.data


# ============================================================
# 結合テスト: 認証
# ============================================================

class TestAuth:

    def test_index_redirects_when_not_logged_in(self, client):
        res = client.get("/")
        assert res.status_code == 302
        assert "/login" in res.headers["Location"]

    def test_login_with_correct_credentials(self, client):
        res = register_and_login(client)
        assert res.status_code == 200
        assert "フォルダ".encode() in res.data

    def test_login_with_wrong_password(self, client):
        do_register(client)
        res = do_login(client, password="wrongpass")
        assert "正しくありません".encode() in res.data

    def test_login_with_unknown_username(self, client):
        res = do_login(client, username="nobody")
        assert "正しくありません".encode() in res.data

    def test_logout(self, client):
        register_and_login(client)
        res = client.post("/logout", follow_redirects=True)
        assert "ログイン".encode() in res.data


# ============================================================
# 結合テスト: フォルダ
# ============================================================

class TestFolder:

    def test_index_shows_folder_list(self, client):
        register_and_login(client)
        res = client.get("/")
        assert res.status_code == 200

    def test_create_folder(self, client):
        register_and_login(client)
        res = create_folder(client, name="企画案")
        assert res.status_code == 200

    def test_folder_saved_to_db(self, client):
        register_and_login(client)
        create_folder(client, name="技術メモ")
        with app.app_context():
            assert Folder.query.filter_by(name="技術メモ").first() is not None

    def test_folder_empty_name(self, client):
        register_and_login(client)
        res = client.post("/folder/new", data={"name": ""}, follow_redirects=True)
        assert "フォルダ名を入力してください".encode() in res.data

    def test_delete_folder(self, client):
        register_and_login(client)
        create_folder(client, name="削除フォルダ")
        with app.app_context():
            folder_id = Folder.query.filter_by(name="削除フォルダ").first().id
        res = client.post(f"/folder/{folder_id}/delete", follow_redirects=True)
        assert res.status_code == 200
        with app.app_context():
            assert Folder.query.get(folder_id) is None

    def test_board_page_accessible(self, client):
        register_and_login(client)
        create_folder(client)
        with app.app_context():
            folder_id = Folder.query.first().id
        res = client.get(f"/folder/{folder_id}")
        assert res.status_code == 200

    def test_all_users_see_all_folders(self, client):
        """全ユーザーが全フォルダを閲覧できること"""
        register_and_login(client, username="userA", password="passA")
        create_folder(client, name="Aのフォルダ")
        client.post("/logout")

        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        res = client.get("/")
        assert "Aのフォルダ".encode() in res.data

    def test_other_user_can_access_folder(self, client):
        """他のユーザーのフォルダにもアクセスできること"""
        register_and_login(client, username="userA", password="passA")
        create_folder(client, name="Aのフォルダ")
        with app.app_context():
            folder_id = Folder.query.first().id
        client.post("/logout")

        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        res = client.get(f"/folder/{folder_id}")
        assert res.status_code == 200


# ============================================================
# 結合テスト: 付箋 CRUD
# ============================================================

class TestMemo:

    def _setup(self, client):
        register_and_login(client)
        create_folder(client)
        with app.app_context():
            return Folder.query.first().id

    def test_create_memo(self, client):
        folder_id = self._setup(client)
        res = create_memo(client, folder_id, title="新しい付箋")
        assert "新しい付箋".encode() in res.data

    def test_memo_saved_to_db(self, client):
        folder_id = self._setup(client)
        create_memo(client, folder_id, title="DB確認")
        with app.app_context():
            assert MemoItem.query.filter_by(title="DB確認").first() is not None

    def test_create_memo_empty_title(self, client):
        folder_id = self._setup(client)
        res = client.post("/memo/new", data={"folder_id": folder_id, "title": "", "body": ""}, follow_redirects=True)
        assert "タイトルを入力してください".encode() in res.data

    def test_update_memo(self, client):
        folder_id = self._setup(client)
        create_memo(client, folder_id, title="元のタイトル")
        with app.app_context():
            memo_id = MemoItem.query.first().id
        res = client.post(f"/memo/{memo_id}", data={"title": "更新後", "body": "更新本文"}, follow_redirects=True)
        assert "更新後".encode() in res.data

    def test_delete_memo(self, client):
        folder_id = self._setup(client)
        create_memo(client, folder_id, title="削除付箋")
        with app.app_context():
            memo_id = MemoItem.query.first().id
        res = client.post(f"/memo/{memo_id}/delete", follow_redirects=True)
        assert "削除付箋".encode() not in res.data

    def test_memo_staggered_position(self, client):
        """付箋を複数作ると位置がずれて配置されること"""
        folder_id = self._setup(client)
        for i in range(3):
            create_memo(client, folder_id, title=f"付箋{i}")
        with app.app_context():
            memos = MemoItem.query.all()
            positions = [(m.pos_x, m.pos_y) for m in memos]
            assert len(set(positions)) == len(positions)


# ============================================================
# 結合テスト: AJAX API
# ============================================================

class TestApi:

    def _setup(self, client):
        register_and_login(client)
        create_folder(client)
        with app.app_context():
            folder_id = Folder.query.first().id
        create_memo(client, folder_id)
        with app.app_context():
            return MemoItem.query.first().id

    def test_update_position(self, client):
        """付箋の座標をAJAXで更新できること"""
        memo_id = self._setup(client)
        res = client.post(f"/api/memo/{memo_id}/position",
                          json={"x": 300, "y": 200},
                          content_type="application/json")
        assert res.status_code == 200
        assert res.get_json()["ok"] is True
        with app.app_context():
            memo = MemoItem.query.get(memo_id)
            assert memo.pos_x == 300
            assert memo.pos_y == 200

    def test_toggle_public(self, client):
        """付箋を公開にするとis_publicがTrueになること"""
        memo_id = self._setup(client)
        res = client.post(f"/api/memo/{memo_id}/toggle-public")
        data = res.get_json()
        assert data["is_public"] is True

    def test_toggle_public_twice_reverts(self, client):
        """2回トグルすると非公開に戻ること"""
        memo_id = self._setup(client)
        client.post(f"/api/memo/{memo_id}/toggle-public")
        res = client.post(f"/api/memo/{memo_id}/toggle-public")
        data = res.get_json()
        assert data["is_public"] is False

    def test_position_api_requires_login(self, client):
        """未ログイン時はAPI 401を返すこと"""
        res = client.post("/api/memo/1/position", json={"x": 0, "y": 0}, content_type="application/json")
        assert res.status_code == 401


# ============================================================
# 結合テスト: 公開/非公開の可視性
# ============================================================

class TestVisibility:

    def test_public_memo_visible_to_other_user(self, client):
        """公開メモは他のユーザーのボードにも表示されること"""
        register_and_login(client, username="userA", password="passA")
        create_folder(client, name="共有ボード")
        with app.app_context():
            folder_id = Folder.query.first().id
        create_memo(client, folder_id, title="公開付箋")
        with app.app_context():
            memo_id = MemoItem.query.first().id
        # 公開に設定
        client.post(f"/api/memo/{memo_id}/toggle-public")
        client.post("/logout")

        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        res = client.get(f"/folder/{folder_id}")
        assert res.status_code == 200
        assert "公開付箋".encode() in res.data

    def test_private_memo_hidden_from_other_user(self, client):
        """非公開メモは他のユーザーのボードには表示されないこと"""
        register_and_login(client, username="userA", password="passA")
        create_folder(client, name="共有ボード")
        with app.app_context():
            folder_id = Folder.query.first().id
        create_memo(client, folder_id, title="秘密の付箋")
        client.post("/logout")

        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        res = client.get(f"/folder/{folder_id}")
        assert "秘密の付箋".encode() not in res.data

    def test_other_user_can_edit_public_memo(self, client):
        """他のユーザーが公開メモを編集できること"""
        register_and_login(client, username="userA", password="passA")
        create_folder(client)
        with app.app_context():
            folder_id = Folder.query.first().id
        create_memo(client, folder_id, title="元のタイトル")
        with app.app_context():
            memo_id = MemoItem.query.first().id
        client.post(f"/api/memo/{memo_id}/toggle-public")
        client.post("/logout")

        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        client.post(f"/memo/{memo_id}", data={"title": "Bが編集", "body": ""}, follow_redirects=True)
        with app.app_context():
            memo = MemoItem.query.get(memo_id)
            assert memo.title == "Bが編集"

    def test_other_user_cannot_edit_private_memo(self, client):
        """他のユーザーが非公開メモを編集できないこと"""
        register_and_login(client, username="userA", password="passA")
        create_folder(client)
        with app.app_context():
            folder_id = Folder.query.first().id
        create_memo(client, folder_id, title="Aの秘密")
        with app.app_context():
            memo_id = MemoItem.query.first().id
        client.post("/logout")

        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        client.post(f"/memo/{memo_id}", data={"title": "Bが書き換え", "body": ""}, follow_redirects=True)
        with app.app_context():
            memo = MemoItem.query.get(memo_id)
            assert memo.title == "Aの秘密"

    def test_only_owner_can_toggle_visibility(self, client):
        """公開/非公開の切り替えはオーナーのみできること"""
        register_and_login(client, username="userA", password="passA")
        create_folder(client)
        with app.app_context():
            folder_id = Folder.query.first().id
        create_memo(client, folder_id, title="Aの付箋")
        with app.app_context():
            memo_id = MemoItem.query.first().id
        # 公開にする
        client.post(f"/api/memo/{memo_id}/toggle-public")
        client.post("/logout")

        # userBがトグルしようとしても失敗（404）
        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        res = client.post(f"/api/memo/{memo_id}/toggle-public")
        assert res.status_code == 404
        # 公開状態のまま変わっていないこと
        with app.app_context():
            memo = MemoItem.query.get(memo_id)
            assert memo.is_public is True


# ============================================================
# 結合テスト: ユーザー分離
# ============================================================

class TestUserIsolation:

    def test_user_cannot_delete_other_users_folder(self, client):
        """ユーザーAのフォルダをユーザーBは削除できないこと"""
        register_and_login(client, username="userA", password="passA")
        create_folder(client, name="Aのフォルダ")
        with app.app_context():
            folder_id = Folder.query.first().id
        client.post("/logout")

        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        res = client.post(f"/folder/{folder_id}/delete", follow_redirects=True)
        assert res.status_code == 404
        with app.app_context():
            assert Folder.query.get(folder_id) is not None

    def test_user_cannot_delete_other_users_private_memo(self, client):
        """ユーザーAの非公開付箋をユーザーBは削除できないこと"""
        register_and_login(client, username="userA", password="passA")
        create_folder(client)
        with app.app_context():
            folder_id = Folder.query.first().id
        create_memo(client, folder_id, title="Aの付箋")
        with app.app_context():
            memo_id = MemoItem.query.first().id
        client.post("/logout")

        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        client.post(f"/memo/{memo_id}/delete")
        with app.app_context():
            assert MemoItem.query.get(memo_id) is not None


# ============================================================
# 結合テスト: 描画ツール API
# ============================================================

class TestDrawing:

    def _setup(self, client):
        """ログイン＋フォルダ作成してfolder_idを返す"""
        register_and_login(client)
        create_folder(client)
        with app.app_context():
            return Folder.query.first().id

    def test_create_pen_drawing(self, client):
        """ペン描画を保存できること"""
        folder_id = self._setup(client)
        res = client.post(f"/api/folder/{folder_id}/drawing",
                          json={"type": "pen", "data": {"points": [[10,10],[20,20],[30,15]]},
                                "color": "#e74c3c", "width": 2},
                          content_type="application/json")
        assert res.status_code == 200
        assert "id" in res.get_json()

    def test_create_arrow_drawing(self, client):
        """矢印を保存できること"""
        folder_id = self._setup(client)
        res = client.post(f"/api/folder/{folder_id}/drawing",
                          json={"type": "arrow", "data": {"x1": 100, "y1": 100, "x2": 300, "y2": 200},
                                "color": "#3498db", "width": 4},
                          content_type="application/json")
        assert res.status_code == 200
        drawing_id = res.get_json()["id"]
        with app.app_context():
            d = Drawing.query.get(drawing_id)
            assert d is not None
            assert d.type == "arrow"

    def test_drawing_saved_to_db(self, client):
        """描画がDBに保存されること"""
        folder_id = self._setup(client)
        client.post(f"/api/folder/{folder_id}/drawing",
                    json={"type": "pen", "data": {"points": [[0,0],[50,50]]},
                          "color": "#000", "width": 2},
                    content_type="application/json")
        with app.app_context():
            assert Drawing.query.filter_by(folder_id=folder_id).count() == 1

    def test_delete_drawing(self, client):
        """自分の描画を削除できること"""
        folder_id = self._setup(client)
        res = client.post(f"/api/folder/{folder_id}/drawing",
                          json={"type": "pen", "data": {"points": [[0,0],[10,10]]},
                                "color": "#000", "width": 2},
                          content_type="application/json")
        drawing_id = res.get_json()["id"]
        del_res = client.delete(f"/api/drawing/{drawing_id}")
        assert del_res.status_code == 200
        with app.app_context():
            assert Drawing.query.get(drawing_id) is None

    def test_delete_other_users_drawing_fails(self, client):
        """他のユーザーの描画は削除できないこと"""
        folder_id = self._setup(client)
        res = client.post(f"/api/folder/{folder_id}/drawing",
                          json={"type": "pen", "data": {"points": [[0,0],[10,10]]},
                                "color": "#000", "width": 2},
                          content_type="application/json")
        drawing_id = res.get_json()["id"]
        client.post("/logout")

        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        del_res = client.delete(f"/api/drawing/{drawing_id}")
        assert del_res.status_code == 404
        with app.app_context():
            assert Drawing.query.get(drawing_id) is not None

    def test_clear_all_drawings(self, client):
        """フォルダの描画を一括削除できること"""
        folder_id = self._setup(client)
        for _ in range(3):
            client.post(f"/api/folder/{folder_id}/drawing",
                        json={"type": "pen", "data": {"points": [[0,0],[10,10]]},
                              "color": "#000", "width": 2},
                        content_type="application/json")
        res = client.delete(f"/api/folder/{folder_id}/drawings")
        assert res.status_code == 200
        with app.app_context():
            assert Drawing.query.filter_by(folder_id=folder_id).count() == 0

    def test_drawing_api_requires_login(self, client):
        """未ログイン時は401を返すこと"""
        res = client.post("/api/folder/1/drawing",
                          json={"type": "pen", "data": {"points": []}, "color": "#000", "width": 2},
                          content_type="application/json")
        assert res.status_code == 401

    def test_drawing_deleted_with_folder(self, client):
        """フォルダ削除時に描画もCASCADE削除されること"""
        folder_id = self._setup(client)
        res = client.post(f"/api/folder/{folder_id}/drawing",
                          json={"type": "pen", "data": {"points": [[0,0]]},
                                "color": "#000", "width": 2},
                          content_type="application/json")
        drawing_id = res.get_json()["id"]
        client.post(f"/folder/{folder_id}/delete")
        with app.app_context():
            assert Drawing.query.get(drawing_id) is None

    def test_board_page_includes_drawings(self, client):
        """ボード画面に描画データが含まれること"""
        folder_id = self._setup(client)
        client.post(f"/api/folder/{folder_id}/drawing",
                    json={"type": "arrow", "data": {"x1": 0, "y1": 0, "x2": 100, "y2": 100},
                          "color": "#e74c3c", "width": 3},
                    content_type="application/json")
        res = client.get(f"/folder/{folder_id}")
        assert b"arrow" in res.data


# ============================================================
# 結合テスト: タグ＆カラーラベル
# ============================================================

class TestTagColor:

    def _setup(self, client):
        register_and_login(client)
        create_folder(client)
        with app.app_context():
            return Folder.query.first().id

    def test_create_memo_with_color(self, client):
        """付箋の色を指定して作成できること"""
        folder_id = self._setup(client)
        client.post("/memo/new", data={
            "folder_id": folder_id, "title": "青い付箋", "body": "",
            "color": "#bfdbfe", "is_public": "false"
        }, follow_redirects=True)
        with app.app_context():
            memo = MemoItem.query.filter_by(title="青い付箋").first()
            assert memo.color == "#bfdbfe"

    def test_create_memo_with_tags(self, client):
        """タグを指定して付箋を作成できること"""
        folder_id = self._setup(client)
        client.post("/memo/new", data={
            "folder_id": folder_id, "title": "タグ付き", "body": "",
            "color": "#fef08a", "tags": "アイデア, 課題", "is_public": "false"
        }, follow_redirects=True)
        with app.app_context():
            memo = MemoItem.query.filter_by(title="タグ付き").first()
            assert "アイデア" in memo.tags
            assert "課題" in memo.tags

    def test_update_memo_color_and_tags(self, client):
        """付箋の色とタグを更新できること"""
        folder_id = self._setup(client)
        create_memo(client, folder_id, title="元の付箋")
        with app.app_context():
            memo_id = MemoItem.query.first().id
        client.post(f"/memo/{memo_id}", data={
            "title": "更新後", "body": "", "color": "#fecdd3", "tags": "更新タグ"
        }, follow_redirects=True)
        with app.app_context():
            memo = MemoItem.query.get(memo_id)
            assert memo.color == "#fecdd3"
            assert "更新タグ" in memo.tags

    def test_board_page_shows_color(self, client):
        """ボード画面に付箋の色が含まれること"""
        folder_id = self._setup(client)
        client.post("/memo/new", data={
            "folder_id": folder_id, "title": "緑付箋", "body": "",
            "color": "#bbf7d0", "is_public": "false"
        }, follow_redirects=True)
        res = client.get(f"/folder/{folder_id}")
        assert b"#bbf7d0" in res.data

    def test_default_color_is_yellow(self, client):
        """色未指定の場合はデフォルト黄色になること"""
        folder_id = self._setup(client)
        create_memo(client, folder_id, title="デフォルト色")
        with app.app_context():
            memo = MemoItem.query.filter_by(title="デフォルト色").first()
            assert memo.color == "#fef08a"


# ============================================================
# 結合テスト: いいね（投票）
# ============================================================

class TestVote:

    def _setup_public_memo(self, client):
        register_and_login(client)
        create_folder(client)
        with app.app_context():
            folder_id = Folder.query.first().id
        client.post("/memo/new", data={
            "folder_id": folder_id, "title": "公開付箋", "body": "",
            "is_public": "true", "color": "#fef08a"
        }, follow_redirects=True)
        with app.app_context():
            return MemoItem.query.first().id

    def test_vote_on_public_memo(self, client):
        """公開付箋にいいねできること"""
        memo_id = self._setup_public_memo(client)
        res = client.post(f"/api/memo/{memo_id}/vote")
        data = res.get_json()
        assert res.status_code == 200
        assert data["voted"] is True
        assert data["count"] == 1

    def test_vote_toggle(self, client):
        """2回投票すると取り消されること"""
        memo_id = self._setup_public_memo(client)
        client.post(f"/api/memo/{memo_id}/vote")
        res = client.post(f"/api/memo/{memo_id}/vote")
        data = res.get_json()
        assert data["voted"] is False
        assert data["count"] == 0

    def test_vote_saved_to_db(self, client):
        """いいねがDBに保存されること"""
        memo_id = self._setup_public_memo(client)
        client.post(f"/api/memo/{memo_id}/vote")
        with app.app_context():
            assert Vote.query.filter_by(memo_id=memo_id).count() == 1

    def test_cannot_vote_on_private_memo(self, client):
        """非公開付箋にはいいねできないこと"""
        register_and_login(client)
        create_folder(client)
        with app.app_context():
            folder_id = Folder.query.first().id
        create_memo(client, folder_id, title="非公開付箋")
        with app.app_context():
            memo_id = MemoItem.query.first().id
        res = client.post(f"/api/memo/{memo_id}/vote")
        assert res.status_code == 403

    def test_vote_requires_login(self, client):
        """未ログイン時は401を返すこと"""
        res = client.post("/api/memo/1/vote")
        assert res.status_code == 401

    def test_multiple_users_can_vote(self, client):
        """複数ユーザーが同じ付箋にいいねできること"""
        memo_id = self._setup_public_memo(client)
        client.post(f"/api/memo/{memo_id}/vote")
        client.post("/logout")

        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        res = client.post(f"/api/memo/{memo_id}/vote")
        assert res.get_json()["count"] == 2


# ============================================================
# 結合テスト: コメント
# ============================================================

class TestComment:

    def _setup_public_memo(self, client):
        register_and_login(client)
        create_folder(client)
        with app.app_context():
            folder_id = Folder.query.first().id
        client.post("/memo/new", data={
            "folder_id": folder_id, "title": "公開付箋", "body": "",
            "is_public": "true", "color": "#fef08a"
        }, follow_redirects=True)
        with app.app_context():
            return MemoItem.query.first().id

    def test_post_comment(self, client):
        """公開付箋にコメントを投稿できること"""
        memo_id = self._setup_public_memo(client)
        res = client.post(f"/api/memo/{memo_id}/comment",
                          json={"body": "良いアイデアですね！"},
                          content_type="application/json")
        assert res.status_code == 200
        data = res.get_json()
        assert data["body"] == "良いアイデアですね！"
        assert "id" in data

    def test_comment_saved_to_db(self, client):
        """コメントがDBに保存されること"""
        memo_id = self._setup_public_memo(client)
        client.post(f"/api/memo/{memo_id}/comment",
                    json={"body": "テストコメント"}, content_type="application/json")
        with app.app_context():
            assert Comment.query.filter_by(memo_id=memo_id).count() == 1

    def test_get_comments(self, client):
        """コメント一覧を取得できること"""
        memo_id = self._setup_public_memo(client)
        client.post(f"/api/memo/{memo_id}/comment",
                    json={"body": "コメント1"}, content_type="application/json")
        client.post(f"/api/memo/{memo_id}/comment",
                    json={"body": "コメント2"}, content_type="application/json")
        res = client.get(f"/api/memo/{memo_id}/comments")
        data = res.get_json()
        assert len(data["comments"]) == 2

    def test_delete_own_comment(self, client):
        """自分のコメントを削除できること"""
        memo_id = self._setup_public_memo(client)
        res = client.post(f"/api/memo/{memo_id}/comment",
                          json={"body": "削除するコメント"}, content_type="application/json")
        comment_id = res.get_json()["id"]
        del_res = client.delete(f"/api/comment/{comment_id}")
        assert del_res.status_code == 200
        with app.app_context():
            assert Comment.query.get(comment_id) is None

    def test_cannot_delete_others_comment(self, client):
        """他ユーザーのコメントは削除できないこと"""
        memo_id = self._setup_public_memo(client)
        res = client.post(f"/api/memo/{memo_id}/comment",
                          json={"body": "Aのコメント"}, content_type="application/json")
        comment_id = res.get_json()["id"]
        client.post("/logout")

        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        del_res = client.delete(f"/api/comment/{comment_id}")
        assert del_res.status_code == 404
        with app.app_context():
            assert Comment.query.get(comment_id) is not None

    def test_cannot_comment_on_private_memo(self, client):
        """非公開付箋にはコメントできないこと"""
        register_and_login(client)
        create_folder(client)
        with app.app_context():
            folder_id = Folder.query.first().id
        create_memo(client, folder_id, title="非公開")
        with app.app_context():
            memo_id = MemoItem.query.first().id
        res = client.post(f"/api/memo/{memo_id}/comment",
                          json={"body": "コメント"}, content_type="application/json")
        assert res.status_code == 403

    def test_empty_comment_rejected(self, client):
        """空のコメントは拒否されること"""
        memo_id = self._setup_public_memo(client)
        res = client.post(f"/api/memo/{memo_id}/comment",
                          json={"body": "  "}, content_type="application/json")
        assert res.status_code == 400

    def test_comment_requires_login(self, client):
        """未ログイン時は401を返すこと"""
        res = client.post("/api/memo/1/comment",
                          json={"body": "test"}, content_type="application/json")
        assert res.status_code == 401

    def test_comment_deleted_with_memo(self, client):
        """付箋削除時にコメントもCASCADE削除されること"""
        memo_id = self._setup_public_memo(client)
        res = client.post(f"/api/memo/{memo_id}/comment",
                          json={"body": "消えるコメント"}, content_type="application/json")
        comment_id = res.get_json()["id"]
        client.post(f"/memo/{memo_id}/delete")
        with app.app_context():
            assert Comment.query.get(comment_id) is None


# ============================================================
# 結合テスト: 貢献スコアランキング
# ============================================================

class TestRanking:

    def _setup(self, client):
        register_and_login(client)
        create_folder(client)
        with app.app_context():
            return Folder.query.first().id

    def test_ranking_requires_login(self, client):
        """未ログイン時は401を返すこと"""
        res = client.get("/api/folder/1/ranking")
        assert res.status_code == 401

    def test_ranking_empty_board(self, client):
        """付箋がない場合は空のランキングを返すこと"""
        folder_id = self._setup(client)
        res = client.get(f"/api/folder/{folder_id}/ranking")
        assert res.status_code == 200
        assert res.get_json()["ranking"] == []

    def test_ranking_scores_public_memo(self, client):
        """公開付箋を追加するとスコア+3されること"""
        folder_id = self._setup(client)
        client.post("/memo/new", data={
            "folder_id": folder_id, "title": "公開", "body": "",
            "is_public": "true", "color": "#fef08a"
        }, follow_redirects=True)
        res = client.get(f"/api/folder/{folder_id}/ranking")
        ranking = res.get_json()["ranking"]
        assert len(ranking) == 1
        assert ranking[0]["score"] == 3

    def test_ranking_scores_vote(self, client):
        """いいねされるとスコア+2されること"""
        folder_id = self._setup(client)
        client.post("/memo/new", data={
            "folder_id": folder_id, "title": "公開", "body": "",
            "is_public": "true", "color": "#fef08a"
        }, follow_redirects=True)
        with app.app_context():
            memo_id = MemoItem.query.first().id
        client.post("/logout")

        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        client.post(f"/api/memo/{memo_id}/vote")

        res = client.get(f"/api/folder/{folder_id}/ranking")
        ranking = res.get_json()["ranking"]
        # userAが公開付箋+3、いいね+2 = 5点
        userA_score = next(r["score"] for r in ranking if r["username"] == "testuser")
        assert userA_score == 5

    def test_ranking_scores_comment(self, client):
        """コメントを投稿するとスコア+1されること"""
        folder_id = self._setup(client)
        client.post("/memo/new", data={
            "folder_id": folder_id, "title": "公開", "body": "",
            "is_public": "true", "color": "#fef08a"
        }, follow_redirects=True)
        with app.app_context():
            memo_id = MemoItem.query.first().id
        client.post("/logout")

        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        client.post(f"/api/memo/{memo_id}/comment",
                    json={"body": "コメント"}, content_type="application/json")

        res = client.get(f"/api/folder/{folder_id}/ranking")
        ranking = res.get_json()["ranking"]
        userB_score = next(r["score"] for r in ranking if r["username"] == "userB")
        assert userB_score == 1

    def test_ranking_sorted_by_score(self, client):
        """スコアの高い順に並ぶこと"""
        folder_id = self._setup(client)
        # userAが2枚の公開付箋（6点）
        for i in range(2):
            client.post("/memo/new", data={
                "folder_id": folder_id, "title": f"付箋{i}", "body": "",
                "is_public": "true", "color": "#fef08a"
            }, follow_redirects=True)
        client.post("/logout")

        # userBが1枚（3点）
        do_register(client, username="userB", password="passB")
        do_login(client, username="userB", password="passB")
        client.post("/memo/new", data={
            "folder_id": folder_id, "title": "Bの付箋", "body": "",
            "is_public": "true", "color": "#fef08a"
        }, follow_redirects=True)

        res = client.get(f"/api/folder/{folder_id}/ranking")
        ranking = res.get_json()["ranking"]
        assert ranking[0]["score"] >= ranking[1]["score"]
        assert ranking[0]["username"] == "testuser"
