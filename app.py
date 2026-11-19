
import os
import re
import sqlite3
import secrets

from contextlib import contextmanager
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, abort
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename


# ==========================================
# 1. د پروژې اساسي تنظیمات
# ==========================================

BASE = os.path.dirname(os.path.abspath(__file__))

DB = os.path.join(BASE, "hakimi_cars.db")

UPLOAD = os.path.join(BASE, "static", "uploads")

os.makedirs(UPLOAD, exist_ok=True)

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    secrets.token_hex(32)
)

MAX_CAR_IMAGES = 10
MAX_IMAGE_SIZE = 12 * 1024 * 1024

app.config["MAX_CONTENT_LENGTH"] = 125 * 1024 * 1024

ALLOWED = {"png", "jpg", "jpeg", "webp"}

ALLOWED_FONTS = {
    "Noto Naskh Arabic",
    "Tahoma",
    "Arial",
    "sans-serif",
    "Georgia"
}

ALLOWED_FONT_SIZES = {
    "14px", "15px", "16px", "17px", "18px",
    "19px", "20px", "22px", "24px"
}

ALLOWED_HERO_SIZES = {
    "20px", "22px", "24px", "26px",
    "28px", "30px", "32px", "36px",
    "40px", "44px", "48px", "50px"
}

ALLOWED_ALIGNMENTS = {
    "center",
    "right",
    "left"
}

ALLOWED_TEMPLATES = {
    "gold",
    "blue",
    "green",
    "dark"
}


@app.after_request
def disable_cache(response):

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )

    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response


# ==========================================
# 2. د Database اتصال
# ==========================================

@contextmanager
def db():

    con = sqlite3.connect(DB)

    con.row_factory = sqlite3.Row

    con.execute("PRAGMA foreign_keys = ON")

    try:

        yield con

        con.commit()

    except Exception:

        con.rollback()

        raise

    finally:

        con.close()


# ==========================================
# 3. د Database د کالمونو اصلاح
# ==========================================

def ensure_column(con, table, column, definition):

    columns = [
        row["name"]
        for row in con.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    ]

    if column not in columns:

        con.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


# ==========================================
# 4. د Settings خوندي کولو عمومي دنده
# ==========================================

def save_setting(con, key, value):

    con.execute("""
        INSERT INTO settings(key, value)
        VALUES(?, ?)

        ON CONFLICT(key)
        DO UPDATE SET value=excluded.value
    """, (key, str(value)))


# ==========================================
# 5. د Pixel ارزښت خوندي کول
# ==========================================

def safe_position(value, minimum, maximum, default=0):

    try:

        number = int(value)

    except (TypeError, ValueError):

        return default

    return max(minimum, min(number, maximum))


# ==========================================
# 6. د Database جوړول او تازه کول
# ==========================================

def init_db():

    with db() as con:

        # د مدیر حسابونه
        con.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)

        # د موټرونو جدول
        con.execute("""
            CREATE TABLE IF NOT EXISTS cars(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                brand TEXT,
                model TEXT,
                year TEXT,
                price TEXT,
                mileage TEXT,
                fuel TEXT,
                transmission TEXT,
                category TEXT,
                color TEXT,
                condition TEXT,
                status TEXT DEFAULT 'موجود',
                description TEXT,
                image TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # نوي تخنیکي مشخصات
        new_columns = {
            "engine": "TEXT",
            "drive": "TEXT",
            "doors": "TEXT",
            "seats": "TEXT",
            "vin": "TEXT",
            "features": "TEXT"
        }

        for column, definition in new_columns.items():

            ensure_column(
                con,
                "cars",
                column,
                definition
            )

        # د موټرونو عکسونه
        con.execute("""
            CREATE TABLE IF NOT EXISTS car_images(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(car_id)
                    REFERENCES cars(id)
                    ON DELETE CASCADE
            )
        """)

        # د ویب‌سایټ تنظیمات
        con.execute("""
            CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # مدیر حساب
        user = con.execute(
            "SELECT id FROM users WHERE username='admin'"
        ).fetchone()

        if not user:

            con.execute("""
                INSERT INTO users(username, password)
                VALUES(?, ?)
            """, (
                "admin",
                generate_password_hash("Hakimi@2026")
            ))

        # لومړني تنظیمات
        defaults = {

            "site_name": "Hakimi Cars",

            "phone": "+93 912 123 456",

            "email": "info@hakimicars.af",

            "address": "کندهار، افغانستان",

            "hero_title": "په حکیمي موټرو نندارتون کې ښه راغلاست!",

            "hero_subtitle": "د لوړ کیفیت موټرونه، مناسب قیمتونه او باوري خدمت",

            "hero_image": "",

            "hero_text_align": "center",

            "hero_text_color": "#ffffff",

            "hero_title_size": "30px",

            "hero_text_x": "0",

            "hero_text_y": "0",

            "font_family": "Noto Naskh Arabic",

            "font_size": "17px",

            "template_style": "gold"
        }

        for key, value in defaults.items():

            con.execute("""
                INSERT OR IGNORE INTO settings(key, value)
                VALUES(?, ?)
            """, (key, value))

        # د پخواني فونټ اندازه اصلاح
        old_font_size = con.execute("""
            SELECT value
            FROM settings
            WHERE key='font_size'
        """).fetchone()

        if old_font_size:

            old_value = str(old_font_size["value"] or "")

            if old_value.isdigit():

                save_setting(
                    con,
                    "font_size",
                    old_value + "px"
                )

        # د پخوانیو موټرونو عکسونه ګالري ته انتقالول
        old_cars = con.execute("""
            SELECT id, image
            FROM cars
            WHERE image IS NOT NULL AND image != ''
        """).fetchall()

        for car in old_cars:

            exists = con.execute("""
                SELECT id
                FROM car_images
                WHERE car_id=? AND filename=?
            """, (
                car["id"],
                car["image"]
            )).fetchone()

            if not exists:

                con.execute("""
                    INSERT INTO car_images(car_id, filename)
                    VALUES(?, ?)
                """, (
                    car["id"],
                    car["image"]
                ))

        # د نمونې موټرونه یوازې که جدول خالي وي
        car_count = con.execute(
            "SELECT COUNT(*) FROM cars"
        ).fetchone()[0]

        if car_count == 0:

            samples = [

                (
                    "Toyota Camry", "Toyota", "Camry", "2022",
                    "$32,500", "42,000 km", "پټرول", "اتومات",
                    "سیډان", "سپین", "کارول شوی", "موجود",
                    "پاک او ښه ساتل شوی موټر", ""
                ),

                (
                    "BMW 530i", "BMW", "530i", "2023",
                    "$48,000", "28,000 km", "پټرول", "اتومات",
                    "لوکس", "تور", "کارول شوی", "موجود",
                    "په ښه حالت کې، بشپړ امکانات", ""
                ),

                (
                    "Lexus LX 600", "Lexus", "LX 600", "2024",
                    "$95,000", "12,000 km", "پټرول", "اتومات",
                    "SUV", "سپین", "کارول شوی", "موجود",
                    "لوړ کیفیت او قوي موټر", ""
                ),

                (
                    "Mercedes-Benz E300", "Mercedes-Benz", "E300", "2023",
                    "$62,000", "35,000 km", "پټرول", "اتومات",
                    "لوکس", "تور", "کارول شوی", "موجود",
                    "ښکلی او ارام موټر", ""
                )
            ]

            con.executemany("""
                INSERT INTO cars(
                    name, brand, model, year, price, mileage,
                    fuel, transmission, category, color,
                    condition, status, description, image
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, samples)


# Database فعالول
init_db()


# ==========================================
# 7. د مدیر د اجازې سیستم
# ==========================================

def admin_required(fn):

    @wraps(fn)
    def wrapped(*args, **kwargs):

        if not session.get("admin_id"):

            return redirect(url_for("login"))

        return fn(*args, **kwargs)

    return wrapped


# ==========================================
# 8. د ویب‌سایټ تنظیمات
# ==========================================

def settings():

    with db() as con:

        rows = con.execute(
            "SELECT * FROM settings"
        ).fetchall()

        result = {
            row["key"]: row["value"]
            for row in rows
        }

        # د پخوانیو ارزښتونو لپاره خوندي اصلي ارزښتونه
        result.setdefault("hero_text_x", "0")
        result.setdefault("hero_text_y", "0")
        result.setdefault("hero_text_color", "#ffffff")
        result.setdefault("hero_text_align", "center")
        result.setdefault("hero_title_size", "30px")
        result.setdefault("template_style", "gold")

        return result


@app.context_processor
def inject_settings():

    return {
        "settings": settings()
    }


# ==========================================
# 9. د عکسونو اعتبار او اپلوډ
# ==========================================

def validate_image(file):

    if not file or not file.filename:

        return "د عکس فایل سم نه دی."

    original_name = secure_filename(file.filename)

    if "." not in original_name:

        return "د عکس فایل بڼه ناسمه ده."

    ext = original_name.rsplit(".", 1)[-1].lower()

    if ext not in ALLOWED:

        return "یوازې JPG، JPEG، PNG او WEBP عکسونه منل کېږي."

    try:

        file.stream.seek(0, os.SEEK_END)

        size = file.stream.tell()

        file.stream.seek(0)

    except (OSError, AttributeError):

        return "د عکس اندازه نه شي لوستل کېدای."

    if size <= 0:

        return "د عکس فایل تش دی."

    if size > MAX_IMAGE_SIZE:

        return "د هر عکس اندازه باید تر ۱۲ MB کمه وي."

    return None


def save_upload(file):

    if not file or not file.filename:

        return ""

    error = validate_image(file)

    if error:

        raise ValueError(error)

    original_name = secure_filename(file.filename)

    ext = original_name.rsplit(".", 1)[-1].lower()

    filename = secrets.token_hex(12) + "." + ext

    path = os.path.join(UPLOAD, filename)

    file.save(path)

    return filename


# ==========================================
# 10. د موټر ګالري
# ==========================================

def get_car_gallery(con, car_id):

    rows = con.execute("""
        SELECT filename
        FROM car_images
        WHERE car_id=?
        ORDER BY id ASC
        LIMIT ?
    """, (
        car_id,
        MAX_CAR_IMAGES
    )).fetchall()

    images = [
        row["filename"]
        for row in rows
    ]

    car = con.execute(
        "SELECT image FROM cars WHERE id=?",
        (car_id,)
    ).fetchone()

    if car and car["image"] and car["image"] not in images:

        images.insert(0, car["image"])

    return images[:MAX_CAR_IMAGES]


# ==========================================
# 11. اصلي پاڼه
# ==========================================

@app.route("/")
def home():

    q = request.args.get("q", "").strip()

    brand = request.args.get("brand", "").strip()

    category = request.args.get("category", "").strip()

    with db() as con:

        sql = "SELECT * FROM cars WHERE 1=1"

        args = []

        if q:

            sql += """
                AND (
                    name LIKE ?
                    OR brand LIKE ?
                    OR model LIKE ?
                )
            """

            args += [f"%{q}%"] * 3

        if brand:

            sql += " AND brand=?"

            args.append(brand)

        if category:

            sql += " AND category=?"

            args.append(category)

        sql += " ORDER BY id DESC"

        cars = con.execute(
            sql,
            args
        ).fetchall()

        brands = [
            row[0]
            for row in con.execute("""
                SELECT DISTINCT brand
                FROM cars
                WHERE brand IS NOT NULL AND brand!=''
                ORDER BY brand
            """)
        ]

        categories = [
            row[0]
            for row in con.execute("""
                SELECT DISTINCT category
                FROM cars
                WHERE category IS NOT NULL AND category!=''
                ORDER BY category
            """)
        ]

    return render_template(
        "index.html",
        cars=cars,
        brands=brands,
        categories=categories,
        settings=settings(),
        q=q,
        selected_brand=brand,
        selected_category=category
    )


# ==========================================
# 12. د موټر تفصیلي پاڼه
# ==========================================

@app.route("/car/<int:car_id>")
def car_detail(car_id):

    with db() as con:

        car = con.execute(
            "SELECT * FROM cars WHERE id=?",
            (car_id,)
        ).fetchone()

        if not car:

            abort(404)

        gallery_images = get_car_gallery(
            con,
            car_id
        )

    return render_template(
        "detail.html",
        car=car,
        gallery_images=gallery_images,
        settings=settings()
    )


# ==========================================
# 13. د مدیر Login
# ==========================================

@app.route("/admin/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        with db() as con:

            user = con.execute(
                "SELECT * FROM users WHERE username=?",
                (username,)
            ).fetchone()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session.clear()

            session["admin_id"] = user["id"]

            session["admin_name"] = user["username"]

            return redirect(url_for("dashboard"))

        flash("یوزرنوم یا پاسورډ ناسم دی.")

    return render_template("login.html")


# ==========================================
# 14. د مدیر Logout
# ==========================================

@app.route("/admin/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# ==========================================
# 15. د مدیر Dashboard
# ==========================================

@app.route("/admin")
@admin_required
def dashboard():

    with db() as con:

        rows = con.execute(
            "SELECT * FROM cars ORDER BY id DESC"
        ).fetchall()

        cars = []

        for row in rows:

            car = dict(row)

            car["gallery_images"] = get_car_gallery(
                con,
                car["id"]
            )

            cars.append(car)

        total = con.execute(
            "SELECT COUNT(*) FROM cars"
        ).fetchone()[0]

        available = con.execute(
            "SELECT COUNT(*) FROM cars WHERE status='موجود'"
        ).fetchone()[0]

        sold = con.execute(
            "SELECT COUNT(*) FROM cars WHERE status='پلورل شوی'"
        ).fetchone()[0]

    return render_template(
        "admin.html",
        cars=cars,
        total=total,
        available=available,
        sold=sold,
        settings=settings()
    )


# ==========================================
# 16. د موټر ثبت او اصلاح
# ==========================================

@app.route("/admin/car/save", methods=["POST"])
@admin_required
def save_car():

    form = request.form

    fields = [
        "name",
        "brand",
        "model",
        "year",
        "price",
        "mileage",
        "fuel",
        "transmission",
        "category",
        "color",
        "condition",
        "status",
        "description",
        "engine",
        "drive",
        "doors",
        "seats",
        "vin",
        "features"
    ]

    values = [
        form.get(key, "").strip()
        for key in fields
    ]

    if not values[0]:

        flash("د موټر نوم حتمي ولیکئ.")

        return redirect(url_for("dashboard"))

    car_id = form.get("id", "").strip()

    selected_files = [
        file
        for file in request.files.getlist("images")
        if file and file.filename
    ]

    old_input = request.files.get("image")

    if old_input and old_input.filename:

        selected_files.append(old_input)

    if len(selected_files) > MAX_CAR_IMAGES:

        flash("یوازې تر ۱۰ پورې عکسونه پورته کېدای شي.")

        return redirect(url_for("dashboard"))

    for file in selected_files:

        error = validate_image(file)

        if error:

            flash(error)

            return redirect(url_for("dashboard"))

    uploaded = []

    try:

        for file in selected_files:

            uploaded.append(save_upload(file))

        with db() as con:

            if car_id:

                existing = con.execute(
                    "SELECT id FROM cars WHERE id=?",
                    (car_id,)
                ).fetchone()

                if not existing:

                    raise ValueError("دا موټر په Database کې پیدا نه شو.")

                old_gallery = get_car_gallery(
                    con,
                    int(car_id)
                )

                if len(old_gallery) + len(uploaded) > MAX_CAR_IMAGES:

                    raise ValueError(
                        "د دې موټر لپاره د ۱۰ عکسونو حد پوره شوی. "
                        "نوي عکسونه نشي ورزیاتېدای."
                    )

                con.execute("""
                    UPDATE cars SET
                        name=?,
                        brand=?,
                        model=?,
                        year=?,
                        price=?,
                        mileage=?,
                        fuel=?,
                        transmission=?,
                        category=?,
                        color=?,
                        condition=?,
                        status=?,
                        description=?,
                        engine=?,
                        drive=?,
                        doors=?,
                        seats=?,
                        vin=?,
                        features=?
                    WHERE id=?
                """, (
                    *values,
                    car_id
                ))

                for filename in uploaded:

                    con.execute("""
                        INSERT INTO car_images(car_id, filename)
                        VALUES(?, ?)
                    """, (
                        car_id,
                        filename
                    ))

                gallery = get_car_gallery(
                    con,
                    int(car_id)
                )

                first_image = gallery[0] if gallery else ""

                con.execute(
                    "UPDATE cars SET image=? WHERE id=?",
                    (first_image, car_id)
                )

            else:

                cursor = con.execute("""
                    INSERT INTO cars(
                        name, brand, model, year, price, mileage,
                        fuel, transmission, category, color,
                        condition, status, description,
                        engine, drive, doors, seats, vin, features,
                        image
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    *values,
                    uploaded[0] if uploaded else ""
                ))

                new_car_id = cursor.lastrowid

                for filename in uploaded:

                    con.execute("""
                        INSERT INTO car_images(car_id, filename)
                        VALUES(?, ?)
                    """, (
                        new_car_id,
                        filename
                    ))

    except (ValueError, sqlite3.Error) as error:

        for filename in uploaded:

            path = os.path.join(UPLOAD, filename)

            if os.path.exists(path):

                try:
                    os.remove(path)
                except OSError:
                    pass

        flash(str(error))

        return redirect(url_for("dashboard"))

    flash("د موټر معلومات او عکسونه په بریالیتوب سره ثبت شول.")

    return redirect(url_for("dashboard"))


# ==========================================
# 17. د موټر حذف
# ==========================================

@app.route("/admin/car/delete/<int:car_id>", methods=["POST"])
@admin_required
def delete_car(car_id):

    with db() as con:

        car = con.execute(
            "SELECT id FROM cars WHERE id=?",
            (car_id,)
        ).fetchone()

        if not car:

            flash("موټر پیدا نه شو.")

            return redirect(url_for("dashboard"))

        con.execute(
            "DELETE FROM cars WHERE id=?",
            (car_id,)
        )

    flash("موټر له Database څخه حذف شو.")

    return redirect(url_for("dashboard"))


# ==========================================
# 18. د ویب‌سایټ تنظیمات
# ==========================================

@app.route("/admin/settings", methods=["POST"])
@admin_required
def update_settings():

    form = request.form

    # عادي متنونه
    text_keys = [
        "site_name",
        "phone",
        "email",
        "address",
        "hero_title",
        "hero_subtitle"
    ]

    new_values = {}

    for key in text_keys:

        new_values[key] = form.get(
            key,
            ""
        ).strip()

    # د فونټ ډول
    font_family = form.get(
        "font_family",
        "Noto Naskh Arabic"
    )

    if font_family not in ALLOWED_FONTS:

        font_family = "Noto Naskh Arabic"

    new_values["font_family"] = font_family

    # د عمومي فونټ اندازه
    font_size = form.get(
        "font_size",
        "17px"
    )

    if font_size not in ALLOWED_FONT_SIZES:

        font_size = "17px"

    new_values["font_size"] = font_size

    # د سرلیک موقعیت
    hero_align = form.get(
        "hero_text_align",
        "center"
    )

    if hero_align not in ALLOWED_ALIGNMENTS:

        hero_align = "center"

    new_values["hero_text_align"] = hero_align

    # د سرلیک رنګ
    hero_color = form.get(
        "hero_text_color",
        "#ffffff"
    ).strip()

    if not re.fullmatch(
        r"#[0-9a-fA-F]{6}",
        hero_color
    ):

        hero_color = "#ffffff"

    new_values["hero_text_color"] = hero_color

    # د سرلیک اندازه
    hero_size = form.get(
        "hero_title_size",
        "30px"
    )

    if hero_size not in ALLOWED_HERO_SIZES:

        hero_size = "30px"

    new_values["hero_title_size"] = hero_size

    # افقي موقعیت: -400 تر 400 Pixel
    hero_x = safe_position(
        form.get("hero_text_x", "0"),
        -400,
        400
    )

    new_values["hero_text_x"] = str(hero_x)

    # عمودي موقعیت: -250 تر 250 Pixel
    hero_y = safe_position(
        form.get("hero_text_y", "0"),
        -250,
        250
    )

    new_values["hero_text_y"] = str(hero_y)

    # د ټیمپلېټ انتخاب
    template_style = form.get(
        "template_style",
        "gold"
    )

    if template_style not in ALLOWED_TEMPLATES:

        template_style = "gold"

    new_values["template_style"] = template_style

    # د Hero عکس اعتبار
    hero_file = request.files.get("hero_image")

    if hero_file and hero_file.filename:

        error = validate_image(hero_file)

        if error:

            flash(error)

            return redirect(url_for("dashboard"))

    uploaded_hero = ""

    try:

        if hero_file and hero_file.filename:

            uploaded_hero = save_upload(hero_file)

        with db() as con:

            for key, value in new_values.items():

                save_setting(
                    con,
                    key,
                    value
                )

            if uploaded_hero:

                save_setting(
                    con,
                    "hero_image",
                    uploaded_hero
                )

    except (ValueError, sqlite3.Error) as error:

        if uploaded_hero:

            path = os.path.join(
                UPLOAD,
                uploaded_hero
            )

            if os.path.exists(path):

                try:
                    os.remove(path)
                except OSError:
                    pass

        flash(str(error))

        return redirect(url_for("dashboard"))

    flash("د ویب‌سایټ ټول تنظیمات په بریالیتوب سره خوندي شول.")

    return redirect(url_for("dashboard"))


# ==========================================
# 19. د مدیر یوزرنوم او پاسورډ
# ==========================================

@app.route("/admin/account", methods=["POST"])
@admin_required
def update_account():

    current_password = request.form.get(
        "current_password",
        ""
    )

    new_username = request.form.get(
        "new_username",
        ""
    ).strip()

    new_password = request.form.get(
        "new_password",
        ""
    )

    confirm_password = request.form.get(
        "confirm_password",
        ""
    )

    if not new_username:

        flash("نوی یوزرنوم ولیکئ.")

        return redirect(url_for("dashboard"))

    if len(new_password) < 8:

        flash("نوی پاسورډ باید لږ تر لږه ۸ توري ولري.")

        return redirect(url_for("dashboard"))

    if new_password != confirm_password:

        flash("نوي پاسورډونه یو شان نه دي.")

        return redirect(url_for("dashboard"))

    with db() as con:

        user = con.execute(
            "SELECT * FROM users WHERE id=?",
            (session["admin_id"],)
        ).fetchone()

        if not user or not check_password_hash(
            user["password"],
            current_password
        ):

            flash("اوسنی پاسورډ ناسم دی.")

            return redirect(url_for("dashboard"))

        try:

            con.execute("""
                UPDATE users
                SET username=?, password=?
                WHERE id=?
            """, (
                new_username,
                generate_password_hash(new_password),
                session["admin_id"]
            ))

        except sqlite3.IntegrityError:

            flash(
                "دا یوزرنوم له مخکې څخه کارول شوی؛ "
                "بل یوزرنوم وټاکئ."
            )

            return redirect(url_for("dashboard"))

    session["admin_name"] = new_username

    flash("یوزرنوم او پاسورډ په بریالیتوب سره بدل شول.")

    return redirect(url_for("dashboard"))


# ==========================================
# 20. د لوی فایل خطا
# ==========================================

@app.errorhandler(413)
def file_too_large(error):

    flash(
        "د عکسونو ټول حجم ډېر زیات دی. "
        "د هر عکس اندازه باید تر ۱۲ MB کمه وي."
    )

    return redirect(url_for("dashboard"))


# ==========================================
# 21. د پروګرام چلول
# ==========================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
