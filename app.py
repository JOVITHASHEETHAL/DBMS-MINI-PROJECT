# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = "invex_super_secret"
DB = "database.db"

# ---------- DB helpers ----------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")  # important
    return db

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB)
    cur = db.cursor()

    # enable foreign key cascade
    cur.execute("PRAGMA foreign_keys = ON")

    # --- admin table ---
    cur.execute("""
      CREATE TABLE IF NOT EXISTS admin (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
      )
    """)
    cur.execute("INSERT OR IGNORE INTO admin (username, password) VALUES (?, ?)", ("admin", "1234"))

    # --- products table ---
    cur.execute("""
      CREATE TABLE IF NOT EXISTS products (
        prod_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        price TEXT,
        stock_qty INTEGER DEFAULT 0
      )
    """)

    # --- suppliers table ---
    cur.execute("""
      CREATE TABLE IF NOT EXISTS suppliers (
        supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact TEXT
      )
    """)

    # --- purchases table (with cascade) ---
    cur.execute("""
      CREATE TABLE IF NOT EXISTS purchases (
        purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
        prod_id INTEGER,
        supplier_id INTEGER,
        quantity INTEGER,
        date TEXT,
        FOREIGN KEY(prod_id) REFERENCES products(prod_id) ON DELETE CASCADE,
        FOREIGN KEY(supplier_id) REFERENCES suppliers(supplier_id) ON DELETE CASCADE
      )
    """)

    db.commit()
    db.close()

init_db()

# ---------- Auth ----------
def is_logged_in():
    return session.get("admin") is not None

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        db = get_db()
        cur = db.execute("SELECT * FROM admin WHERE username=? AND password=?", (username, password))
        row = cur.fetchone()
        if row:
            session["admin"] = username
            flash("Login successful", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "error")
            return render_template("login.html")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    flash("Logged out", "info")
    return redirect(url_for("login"))

# ---------- Dashboard ----------
@app.route("/dashboard")
def dashboard():
    if not is_logged_in():
        return redirect(url_for("login"))
    db = get_db()
    total_products = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_suppliers = db.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
    low_stock_count = db.execute("SELECT COUNT(*) FROM products WHERE stock_qty < 10").fetchone()[0]
    recent_purchases = db.execute("""
        SELECT p.purchase_id, pr.name AS product, s.name AS supplier, p.quantity, p.date
        FROM purchases p
        LEFT JOIN products pr ON p.prod_id = pr.prod_id
        LEFT JOIN suppliers s ON p.supplier_id = s.supplier_id
        ORDER BY p.date DESC, p.purchase_id DESC
        LIMIT 5
    """).fetchall()
    return render_template("dashboard.html",
                           admin=session.get("admin"),
                           total_products=total_products,
                           total_suppliers=total_suppliers,
                           low_stock_count=low_stock_count,
                           recent_purchases=recent_purchases)

# ---------- Products ----------
@app.route("/products", methods=["GET"])
def products():
    if not is_logged_in():
        return redirect(url_for("login"))
    db = get_db()
    items = db.execute("SELECT * FROM products ORDER BY prod_id DESC").fetchall()
    return render_template("products.html", products=items)

@app.route("/products/add", methods=["POST"])
def add_product():
    if not is_logged_in():
        return redirect(url_for("login"))
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    price = request.form.get("price", "").strip()
    stock_qty = request.form.get("stock_qty") or 0
    db = get_db()
    db.execute("INSERT INTO products (name, category, price, stock_qty) VALUES (?, ?, ?, ?)",
               (name, category, price, int(stock_qty)))
    db.commit()
    flash("Product added", "success")
    return redirect(url_for("products"))

@app.route("/products/update/<int:prod_id>", methods=["POST"])
def update_product(prod_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    price = request.form.get("price", "").strip()
    stock_qty = request.form.get("stock_qty") or 0
    db = get_db()
    db.execute("""UPDATE products SET name=?, category=?, price=?, stock_qty=? WHERE prod_id=?""",
               (name, category, price, int(stock_qty), prod_id))
    db.commit()
    flash("Product updated", "success")
    return redirect(url_for("products"))

@app.route("/products/delete/<int:prod_id>", methods=["POST"])
def delete_product(prod_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    db = get_db()
    db.execute("DELETE FROM products WHERE prod_id=?", (prod_id,))
    db.commit()
    flash("Product deleted", "info")
    return redirect(url_for("products"))

# ---------- Suppliers ----------
@app.route("/suppliers")
def suppliers():
    if not is_logged_in():
        return redirect(url_for("login"))
    db = get_db()
    items = db.execute("SELECT * FROM suppliers ORDER BY supplier_id DESC").fetchall()
    return render_template("suppliers.html", suppliers=items)

@app.route("/suppliers/add", methods=["POST"])
def add_supplier():
    if not is_logged_in():
        return redirect(url_for("login"))
    name = request.form.get("name", "").strip()
    contact = request.form.get("contact", "").strip()
    db = get_db()
    db.execute("INSERT INTO suppliers (name, contact) VALUES (?, ?)", (name, contact))
    db.commit()
    flash("Supplier added", "success")
    return redirect(url_for("suppliers"))

@app.route("/suppliers/delete/<int:supplier_id>", methods=["POST"])
def delete_supplier(supplier_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    db = get_db()
    db.execute("DELETE FROM suppliers WHERE supplier_id=?", (supplier_id,))
    db.commit()
    flash("Supplier deleted", "info")
    return redirect(url_for("suppliers"))

# ---------- Purchases ----------
@app.route("/purchases")
def purchases():
    if not is_logged_in():
        return redirect(url_for("login"))
    db = get_db()
    purchases = db.execute("""
        SELECT p.purchase_id, pr.name AS product, s.name AS supplier, p.quantity, p.date
        FROM purchases p
        LEFT JOIN products pr ON p.prod_id = pr.prod_id
        LEFT JOIN suppliers s ON p.supplier_id = s.supplier_id
        ORDER BY p.date DESC, p.purchase_id DESC
    """).fetchall()
    products = db.execute("SELECT * FROM products").fetchall()
    suppliers = db.execute("SELECT * FROM suppliers").fetchall()
    return render_template("purchases.html", purchases=purchases, products=products, suppliers=suppliers)

@app.route("/purchases/add", methods=["POST"])
def add_purchase():
    if not is_logged_in():
        return redirect(url_for("login"))
    prod_id = int(request.form.get("prod_id"))
    supplier_id = int(request.form.get("supplier_id"))
    quantity = int(request.form.get("quantity"))
    purchase_date = request.form.get("date") or date.today().isoformat()

    db = get_db()
    db.execute("INSERT INTO purchases (prod_id, supplier_id, quantity, date) VALUES (?, ?, ?, ?)",
               (prod_id, supplier_id, quantity, purchase_date))
    db.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE prod_id = ?", (quantity, prod_id))
    db.commit()
    flash("Purchase recorded and stock updated", "success")
    return redirect(url_for("purchases"))

# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True)
