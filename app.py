import json as _json
from flask import Flask, request, redirect, url_for, render_template, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app: Flask = Flask(__name__)
app.secret_key = "memo-app-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///memo.sqlite"
db: SQLAlchemy = SQLAlchemy(app)


# ============================================================
# データモデル
# ============================================================

class User(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    username: str = db.Column(db.Text, nullable=False, unique=True)
    password_hash: str = db.Column(db.Text, nullable=False)


class Folder(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.Text, nullable=False)
    user_id: int = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    owner = db.relationship("User", foreign_keys=[user_id])
    memos = db.relationship("MemoItem", backref="folder", cascade="all, delete-orphan")
    drawings = db.relationship("Drawing", backref="folder", cascade="all, delete-orphan")


class MemoItem(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    title: str = db.Column(db.Text, nullable=False)
    body: str = db.Column(db.Text, nullable=False)
    color: str = db.Column(db.Text, nullable=False, default="#fef08a")
    tags: str = db.Column(db.Text, nullable=True)
    pos_x: int = db.Column(db.Integer, nullable=False, default=40)
    pos_y: int = db.Column(db.Integer, nullable=False, default=40)
    is_public: bool = db.Column(db.Boolean, nullable=False, default=False)
    updated_at: datetime = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    user_id: int = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    folder_id: int = db.Column(db.Integer, db.ForeignKey("folder.id"), nullable=False)
    votes = db.relationship("Vote", cascade="all, delete-orphan")
    comments = db.relationship("Comment", cascade="all, delete-orphan")


class Vote(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    memo_id: int = db.Column(db.Integer, db.ForeignKey("memo_item.id"), nullable=False)
    user_id: int = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at: datetime = db.Column(db.DateTime, default=datetime.now)
    __table_args__ = (db.UniqueConstraint("memo_id", "user_id", name="uq_vote_memo_user"),)


class Comment(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    memo_id: int = db.Column(db.Integer, db.ForeignKey("memo_item.id"), nullable=False)
    user_id: int = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body: str = db.Column(db.Text, nullable=False)
    created_at: datetime = db.Column(db.DateTime, default=datetime.now)
    author = db.relationship("User", foreign_keys=[user_id])


class Drawing(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    folder_id: int = db.Column(db.Integer, db.ForeignKey("folder.id"), nullable=False)
    user_id: int = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    type: str = db.Column(db.Text, nullable=False)
    data: str = db.Column(db.Text, nullable=False)
    color: str = db.Column(db.Text, nullable=False, default="#e74c3c")
    width: int = db.Column(db.Integer, nullable=False, default=3)
    created_at: datetime = db.Column(db.DateTime, default=datetime.now)


with app.app_context():
    db.create_all()


# ============================================================
# ヘルパー
# ============================================================

def is_logged_in() -> bool:
    return session.get("logged_in", False)

def current_user_id() -> int:
    return session.get("user_id")


# ============================================================
# 認証
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username:
            flash("ログインIDを入力してください")
            return render_template("register.html")
        if not password:
            flash("パスワードを入力してください")
            return render_template("register.html")
        if User.query.filter_by(username=username).first():
            flash("そのログインIDはすでに使用されています")
            return render_template("register.html")
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash("アカウントを登録しました。ログインしてください", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["logged_in"] = True
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("index"))
        flash("ログインIDまたはパスワードが正しくありません")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ============================================================
# フォルダ（全ユーザー共有）
# ============================================================

@app.route("/")
def index():
    if not is_logged_in():
        return redirect(url_for("login"))
    folders = Folder.query.all()
    return render_template("index.html", folders=folders, current_user_id=current_user_id())


@app.route("/folder/new", methods=["POST"])
def folder_new():
    if not is_logged_in():
        return redirect(url_for("login"))
    name = request.form.get("name", "").strip()
    if not name:
        flash("フォルダ名を入力してください")
        return redirect(url_for("index"))
    folder = Folder(name=name, user_id=current_user_id())
    db.session.add(folder)
    db.session.commit()
    return redirect(url_for("board", folder_id=folder.id))


@app.route("/folder/<int:folder_id>/delete", methods=["POST"])
def folder_delete(folder_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    folder = Folder.query.filter_by(id=folder_id, user_id=current_user_id()).first_or_404()
    db.session.delete(folder)
    db.session.commit()
    return redirect(url_for("index"))


# ============================================================
# コルクボード
# ============================================================

@app.route("/folder/<int:folder_id>")
def board(folder_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    folder = Folder.query.filter_by(id=folder_id).first_or_404()
    q = request.args.get("q", "")
    uid = current_user_id()
    query = MemoItem.query.filter(
        MemoItem.folder_id == folder_id,
        db.or_(MemoItem.is_public == True, MemoItem.user_id == uid)
    )
    if q:
        query = query.filter(
            db.or_(MemoItem.title.contains(q), MemoItem.body.contains(q))
        )
    memos = query.all()

    memo_ids = [m.id for m in memos]
    vote_counts = {}
    user_voted = set()
    if memo_ids:
        vc_rows = db.session.query(Vote.memo_id, func.count(Vote.id)) \
            .filter(Vote.memo_id.in_(memo_ids)) \
            .group_by(Vote.memo_id).all()
        vote_counts = {row[0]: row[1] for row in vc_rows}
        uv_rows = Vote.query.filter(Vote.memo_id.in_(memo_ids), Vote.user_id == uid).all()
        user_voted = {v.memo_id for v in uv_rows}

    drawings = Drawing.query.filter_by(folder_id=folder_id).all()
    drawings_json = _json.dumps([{
        "id": d.id, "type": d.type,
        "data": _json.loads(d.data),
        "color": d.color, "width": d.width, "user_id": d.user_id
    } for d in drawings])

    return render_template("board.html", folder=folder, memos=memos, q=q,
                           current_user_id=uid, drawings_json=drawings_json,
                           vote_counts=vote_counts, user_voted=user_voted)


# ============================================================
# 付箋（メモ）
# ============================================================

@app.route("/memo/new", methods=["POST"])
def memo_new():
    if not is_logged_in():
        return redirect(url_for("login"))
    folder_id = request.form.get("folder_id", type=int)
    Folder.query.filter_by(id=folder_id).first_or_404()
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "")
    if not title:
        flash("タイトルを入力してください")
        return redirect(url_for("board", folder_id=folder_id))
    is_public = request.form.get("is_public") == "true"
    color = request.form.get("color", "#fef08a")
    tags = request.form.get("tags", "").strip() or None
    count = MemoItem.query.filter_by(folder_id=folder_id).count()
    pos_x = 40 + (count % 5) * 220
    pos_y = 40 + (count // 5) * 160
    memo = MemoItem(
        title=title, body=body,
        color=color, tags=tags,
        pos_x=pos_x, pos_y=pos_y,
        is_public=is_public,
        user_id=current_user_id(), folder_id=folder_id
    )
    db.session.add(memo)
    db.session.commit()
    return redirect(url_for("board", folder_id=folder_id))


@app.route("/memo/<int:id>", methods=["POST"])
def memo_update(id):
    if not is_logged_in():
        return redirect(url_for("login"))
    memo = MemoItem.query.filter_by(id=id).first_or_404()
    uid = current_user_id()
    if not memo.is_public and memo.user_id != uid:
        return redirect(url_for("board", folder_id=memo.folder_id))
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "")
    if not title:
        flash("タイトルを入力してください")
        return redirect(url_for("board", folder_id=memo.folder_id))
    memo.title = title
    memo.body = body
    memo.color = request.form.get("color", memo.color)
    memo.tags = request.form.get("tags", "").strip() or None
    memo.updated_at = datetime.now()
    db.session.commit()
    return redirect(url_for("board", folder_id=memo.folder_id))


@app.route("/memo/<int:id>/delete", methods=["POST"])
def memo_delete(id):
    if not is_logged_in():
        return redirect(url_for("login"))
    memo = MemoItem.query.filter_by(id=id).first_or_404()
    uid = current_user_id()
    if not memo.is_public and memo.user_id != uid:
        return redirect(url_for("board", folder_id=memo.folder_id))
    folder_id = memo.folder_id
    db.session.delete(memo)
    db.session.commit()
    return redirect(url_for("board", folder_id=folder_id))


# ============================================================
# AJAX API - 付箋
# ============================================================

@app.route("/api/memo/<int:id>/position", methods=["POST"])
def api_memo_position(id):
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    memo = MemoItem.query.filter_by(id=id).first_or_404()
    uid = current_user_id()
    if not memo.is_public and memo.user_id != uid:
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json()
    memo.pos_x = max(0, int(data.get("x", memo.pos_x)))
    memo.pos_y = max(0, int(data.get("y", memo.pos_y)))
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/memo/<int:id>/toggle-public", methods=["POST"])
def api_toggle_public(id):
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    memo = MemoItem.query.filter_by(id=id, user_id=current_user_id()).first_or_404()
    memo.is_public = not memo.is_public
    db.session.commit()
    return jsonify({"is_public": memo.is_public})


# ============================================================
# AJAX API - いいね
# ============================================================

@app.route("/api/memo/<int:id>/vote", methods=["POST"])
def api_vote(id):
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    memo = MemoItem.query.filter_by(id=id).first_or_404()
    if not memo.is_public:
        return jsonify({"error": "forbidden"}), 403
    uid = current_user_id()
    existing = Vote.query.filter_by(memo_id=id, user_id=uid).first()
    if existing:
        db.session.delete(existing)
        voted = False
    else:
        db.session.add(Vote(memo_id=id, user_id=uid))
        voted = True
    db.session.commit()
    count = Vote.query.filter_by(memo_id=id).count()
    return jsonify({"voted": voted, "count": count})


# ============================================================
# AJAX API - コメント
# ============================================================

@app.route("/api/memo/<int:id>/comments")
def api_comments_get(id):
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    MemoItem.query.filter_by(id=id).first_or_404()
    comments = Comment.query.filter_by(memo_id=id).order_by(Comment.created_at).all()
    return jsonify({"comments": [
        {
            "id": c.id,
            "username": c.author.username,
            "user_id": c.user_id,
            "body": c.body,
            "created_at": c.created_at.strftime("%Y/%m/%d %H:%M") if c.created_at else ""
        }
        for c in comments
    ]})


@app.route("/api/memo/<int:id>/comment", methods=["POST"])
def api_comment_create(id):
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    memo = MemoItem.query.filter_by(id=id).first_or_404()
    if not memo.is_public:
        return jsonify({"error": "forbidden"}), 403
    body = (request.get_json() or {}).get("body", "").strip()
    if not body:
        return jsonify({"error": "empty"}), 400
    uid = current_user_id()
    comment = Comment(memo_id=id, user_id=uid, body=body)
    db.session.add(comment)
    db.session.commit()
    user = User.query.get(uid)
    return jsonify({
        "id": comment.id,
        "username": user.username,
        "user_id": uid,
        "body": comment.body,
        "created_at": comment.created_at.strftime("%Y/%m/%d %H:%M") if comment.created_at else ""
    })


@app.route("/api/comment/<int:id>", methods=["DELETE"])
def api_comment_delete(id):
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    comment = Comment.query.filter_by(id=id, user_id=current_user_id()).first_or_404()
    db.session.delete(comment)
    db.session.commit()
    return jsonify({"ok": True})


# ============================================================
# AJAX API - 貢献スコアランキング
# ============================================================

@app.route("/api/folder/<int:folder_id>/ranking")
def api_ranking(folder_id):
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    Folder.query.filter_by(id=folder_id).first_or_404()

    scores = {}
    public_memos = MemoItem.query.filter_by(folder_id=folder_id, is_public=True).all()
    memo_ids = [m.id for m in public_memos]
    memo_author = {m.id: m.user_id for m in public_memos}

    for memo in public_memos:
        scores[memo.user_id] = scores.get(memo.user_id, 0) + 3

    if memo_ids:
        for vote in Vote.query.filter(Vote.memo_id.in_(memo_ids)).all():
            author_id = memo_author.get(vote.memo_id)
            if author_id:
                scores[author_id] = scores.get(author_id, 0) + 2
        for comment in Comment.query.filter(Comment.memo_id.in_(memo_ids)).all():
            scores[comment.user_id] = scores.get(comment.user_id, 0) + 1

    all_user_ids = set(scores.keys())
    usernames = {u.id: u.username for u in User.query.filter(User.id.in_(all_user_ids)).all()}

    ranking = sorted([
        {"user_id": uid, "username": usernames.get(uid, "?"), "score": score}
        for uid, score in scores.items()
    ], key=lambda x: -x["score"])

    return jsonify({"ranking": ranking, "current_user_id": current_user_id()})


# ============================================================
# AJAX API - 描画
# ============================================================

@app.route("/api/folder/<int:folder_id>/drawing", methods=["POST"])
def api_drawing_create(folder_id):
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    Folder.query.filter_by(id=folder_id).first_or_404()
    payload = request.get_json()
    drawing = Drawing(
        folder_id=folder_id,
        user_id=current_user_id(),
        type=payload.get("type", "pen"),
        data=_json.dumps(payload.get("data", {})),
        color=payload.get("color", "#e74c3c"),
        width=int(payload.get("width", 3))
    )
    db.session.add(drawing)
    db.session.commit()
    return jsonify({"id": drawing.id})


@app.route("/api/drawing/<int:id>", methods=["DELETE"])
def api_drawing_delete(id):
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    drawing = Drawing.query.filter_by(id=id, user_id=current_user_id()).first_or_404()
    db.session.delete(drawing)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/folder/<int:folder_id>/drawings", methods=["DELETE"])
def api_drawings_clear(folder_id):
    if not is_logged_in():
        return jsonify({"error": "unauthorized"}), 401
    Folder.query.filter_by(id=folder_id).first_or_404()
    Drawing.query.filter_by(folder_id=folder_id).delete()
    db.session.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=8888)
