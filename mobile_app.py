from flask import Flask, render_template, request, redirect, session,jsonify
import mysql.connector as mc
import os
import uuid
from werkzeug.utils import secure_filename
import random

app = Flask(__name__)
app.secret_key = "secret"

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# フォルダが無ければ自動作成
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def get_db():
    return mc.connect(
        host="localhost",
        user="root",
        password="root",
        database="hew"
    )

@app.route("/")
def index():
    return redirect("/mobile/login")


# --------------------
# ログイン
# --------------------

@app.route("/mobile/login", methods=["GET","POST"])
def mobile_login():

    if request.method == "POST":

        user_id = request.form["user_id"]
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        sql = "SELECT * FROM users WHERE user_id=%s AND password=%s"
        cursor.execute(sql,(user_id,password))

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            return redirect("/mobile/profile")

    return render_template("mobile_login.html")


# --------------------
# 新規登録
# --------------------

@app.route("/mobile/register", methods=["GET","POST"])
def mobile_register():

    if request.method == "POST":

        user_id = request.form["user_id"]
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()

        sql = "INSERT INTO users (user_id,password) VALUES (%s,%s)"
        cursor.execute(sql,(user_id,password))

        conn.commit()

        cursor.close()
        conn.close()

        return redirect("/mobile/login")

    return render_template("mobile_register.html")


# --------------------
# 投稿画面
# --------------------

@app.route("/mobile/post")
def mobile_post():

    if "user_id" not in session:
        return redirect("/mobile/login")

    return render_template("mobile_post.html")


# --------------------
# 投稿処理
# --------------------

## 投稿処理
@app.route("/create_post", methods=["POST"])
def create_post():
    if "user_id" not in session:
        return redirect("/mobile/login")

    title = request.form["title"]
    comment = request.form["comment"]
    image = request.files["image"]

    image_path = None

    if image and image.filename != "":
        filename = secure_filename(image.filename)
        unique_name = str(uuid.uuid4()) + "_" + filename
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        image.save(save_path)
        image_path = "uploads/" + unique_name

    conn = get_db()
    cursor = conn.cursor()

    # 今の最大いいね数を取得
    cursor.execute("SELECT MAX(fake_likes) FROM posts")
    max_likes = cursor.fetchone()[0]

    if max_likes is None:
        max_likes = 3000

    # +α
    alpha = random.randint(-100, 150)
    new_likes = max_likes + alpha

    sql = """
        INSERT INTO posts (user_id, title, comment, image_path, theme, fake_likes)
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    cursor.execute(
        sql,
        (session["user_id"], title, comment, image_path, "秋", new_likes)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return redirect("/mobile/profile")




# =========================
# スマホプロフィール表示
# =========================
@app.route("/mobile/profile")
def mobile_profile():

    if "user_id" not in session:
        return redirect("/mobile/login")

    user_id = session["user_id"]

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # ユーザー情報
    cursor.execute("""
        SELECT id, user_id, bio, icon_path
        FROM users
        WHERE id=%s
    """, (user_id,))
    user = cursor.fetchone()

    # 投稿取得
    cursor.execute("""
        SELECT *
        FROM posts
        WHERE user_id=%s
        ORDER BY created_at DESC
    """, (user_id,))
    posts = cursor.fetchall()

    post_count = len(posts)

    # フォロワー
    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM follows
        WHERE followed_id=%s
    """, (user_id,))
    follower_count = cursor.fetchone()["count"]

    # フォロー
    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM follows
        WHERE follower_id=%s
    """, (user_id,))
    following_count = cursor.fetchone()["count"]

    # バッジ取得
    cursor.execute("""
        SELECT b.badge_name, b.image_path, t.name
        FROM user_badges ub
        JOIN badges b ON ub.badge_id = b.id
        JOIN themes t ON b.theme_id = t.id
        WHERE ub.user_id = %s
        ORDER BY t.id, b.rank_position
    """, (user_id,))

    badges = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "mobile_profile.html",
        user=user,
        posts=posts,
        post_count=post_count,
        follower_count=follower_count,
        following_count=following_count,
        badges=badges
    )


# =========================
# 自己紹介更新
# =========================
@app.route("/mobile/update_bio", methods=["POST"])
def mobile_update_bio():

    if "user_id" not in session:
        return jsonify({"success": False})

    data = request.get_json()
    bio = data.get("bio","")[:150]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET bio=%s WHERE id=%s",
        (bio, session["user_id"])
    )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "success": True,
        "bio": bio
    })


# =========================
# アイコン更新
# =========================
@app.route("/mobile/update_icon", methods=["POST"])
def mobile_update_icon():

    if "user_id" not in session:
        return jsonify({"success": False})

    if "icon" not in request.files:
        return jsonify({"success": False})

    file = request.files["icon"]

    if file.filename == "":
        return jsonify({"success": False})

    filename = secure_filename(file.filename)
    unique_name = str(uuid.uuid4()) + "_" + filename

    save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
    file.save(save_path)

    icon_path = "uploads/" + unique_name

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET icon_path=%s WHERE id=%s",
        (icon_path, session["user_id"])
    )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "success": True,
        "icon_path": icon_path
    })


# =========================
# フォロー / アンフォロー
# =========================
@app.route("/mobile/toggle_follow/<int:target_id>", methods=["POST"])
def mobile_toggle_follow(target_id):

    if "user_id" not in session:
        return jsonify({"error": "login required"}), 401

    my_id = session["user_id"]

    if my_id == target_id:
        return jsonify({"error": "cannot follow yourself"}), 400

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM follows
        WHERE follower_id=%s AND followed_id=%s
    """, (my_id, target_id))

    existing = cursor.fetchone()

    if existing:

        cursor.execute("""
            DELETE FROM follows
            WHERE follower_id=%s AND followed_id=%s
        """, (my_id, target_id))

        conn.commit()
        following = False

    else:

        cursor.execute("""
            INSERT INTO follows (follower_id, followed_id)
            VALUES (%s,%s)
        """, (my_id, target_id))

        conn.commit()
        following = True

    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM follows
        WHERE followed_id=%s
    """, (target_id,))

    follower_count = cursor.fetchone()["count"]

    cursor.close()
    conn.close()

    return jsonify({
        "following": following,
        "follower_count": follower_count,
    })


# --------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=5000,debug=True)