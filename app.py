import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText

# ---------------- CONFIG ----------------
app = Flask(__name__)
app.secret_key = "swastik_pharma_secret_key_change_this"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///swastik.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
db = SQLAlchemy(app)

ADMIN_PASSWORD = "SWASTIK6263"
BUSINESS_EMAIL = "swastikpharmabyt@gmail.com"
WHATSAPP_NUMBER = "919171406630"  # country code + number, no + or spaces

# Gmail SMTP settings (use an App Password, not your normal Gmail password)
SMTP_EMAIL = "swastikpharmabyt@gmail.com"
SMTP_APP_PASSWORD = "PUT_YOUR_16_CHAR_APP_PASSWORD_HERE"  # generate from Google Account > Security > App Passwords

BUSINESS_INFO = {
    "name": "SWASTIK PHARMA",
    "address": "NEAR TANWANI BUILDING, MAHASATI WARD, BHATAPARA 493118, DIST. BALODA-BAZAR BHATAPARA, CHHATTISGARH",
    "mobile1": "+91 62634-06630",
    "mobile2": "+91 91714-06630",
    "email": "swastikpharmabyt@gmail.com",
    "dl_no": "WLF20B2026CT000022 / WLF21B2026CT000020",
    "gstin": "22BYGPJ9942R1ZO",
    "food_licence": "20526031000039"
}

# ---------------- MODELS ----------------
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    salt = db.Column(db.String(200))          # combination / formula
    brand = db.Column(db.String(100))
    category = db.Column(db.String(50))       # Tablets, Syrups etc.
    mrp = db.Column(db.Float, default=0.0)
    ptr = db.Column(db.Float, default=0.0)
    image = db.Column(db.String(200), default="default.png")
    is_new = db.Column(db.Boolean, default=False)
    is_top = db.Column(db.Boolean, default=False)
    is_offer = db.Column(db.Boolean, default=False)
    offer_text = db.Column(db.String(200), default="")

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_name = db.Column(db.String(150))
    dl_number = db.Column(db.String(100))
    mobile = db.Column(db.String(20), unique=True)
    email = db.Column(db.String(150), unique=True)
    address = db.Column(db.String(300))
    password_hash = db.Column(db.String(300))
    profile_complete = db.Column(db.Boolean, default=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    items_summary = db.Column(db.Text)
    total_items = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ---------------- HELPERS ----------------
def send_email(subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = SMTP_EMAIL
        msg['To'] = BUSINESS_EMAIL
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
            server.sendmail(SMTP_EMAIL, BUSINESS_EMAIL, msg.as_string())
    except Exception as e:
        print("Email sending failed:", e)

def current_customer():
    cid = session.get('customer_id')
    if cid:
        return Customer.query.get(cid)
    return None

CATEGORIES = ["Tablets", "Capsules", "Syrups", "Ointment", "Injections", "Drops", "Surgical Products", "Others"]

# ---------------- ROUTES: PUBLIC ----------------
@app.route('/')
def home():
    new_launches = Product.query.filter_by(is_new=True).all()
    top_selling = Product.query.filter_by(is_top=True).all()
    offers = Product.query.filter_by(is_offer=True).all()
    return render_template('index.html', business=BUSINESS_INFO,
                            new_launches=new_launches, top_selling=top_selling,
                            offers=offers, whatsapp=WHATSAPP_NUMBER)

@app.route('/products')
def products():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '')
    products_q = Product.query
    if category and category != "All":
        products_q = products_q.filter_by(category=category)
    if query:
        like = f"%{query}%"
        products_q = products_q.filter(
            (Product.name.ilike(like)) |
            (Product.salt.ilike(like)) |
            (Product.brand.ilike(like))
        )
    all_products = products_q.all()
    return render_template('products.html', products=all_products,
                            categories=CATEGORIES, business=BUSINESS_INFO,
                            selected_category=category, query=query)

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    cart = session.get('cart', {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    session['cart'] = cart
    flash("Item added to cart", "success")
    return redirect(request.referrer or url_for('products'))

@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    items = []
    total_mrp = 0
    for pid, qty in cart.items():
        product = Product.query.get(int(pid))
        if product:
            subtotal = product.mrp * qty
            total_mrp += subtotal
            items.append({"product": product, "qty": qty, "subtotal": subtotal})
    return render_template('cart.html', items=items, total_mrp=total_mrp,
                            business=BUSINESS_INFO, whatsapp=WHATSAPP_NUMBER)

@app.route('/update_cart/<int:product_id>/<action>')
def update_cart(product_id, action):
    cart = session.get('cart', {})
    pid = str(product_id)
    if pid in cart:
        if action == 'increase':
            cart[pid] += 1
        elif action == 'decrease':
            cart[pid] -= 1
            if cart[pid] <= 0:
                del cart[pid]
        elif action == 'remove':
            del cart[pid]
    session['cart'] = cart
    return redirect(url_for('view_cart'))

@app.route('/checkout')
def checkout():
    customer = current_customer()
    if not customer or not customer.profile_complete:
        flash("Please complete your profile before ordering.", "warning")
        return redirect(url_for('signup'))

    cart = session.get('cart', {})
    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect(url_for('view_cart'))

    lines = [f"*New Order from {customer.shop_name}*",
              f"Mobile: {customer.mobile}", f"Address: {customer.address}", ""]
    total_items = 0
    for pid, qty in cart.items():
        product = Product.query.get(int(pid))
        if product:
            lines.append(f"{product.name} ({product.brand}) x {qty} - MRP ₹{product.mrp}")
            total_items += qty

    order_text = "\n".join(lines)

    order = Order(customer_id=customer.id, items_summary=order_text, total_items=total_items)
    db.session.add(order)
    db.session.commit()
    session['cart'] = {}

    import urllib.parse
    wa_message = urllib.parse.quote(order_text)
    wa_link = f"https://wa.me/{WHATSAPP_NUMBER}?text={wa_message}"
    return render_template('cart.html', items=[], total_mrp=0, order_placed=True,
                            wa_link=wa_link, business=BUSINESS_INFO, whatsapp=WHATSAPP_NUMBER)

# ---------------- ROUTES: CUSTOMER AUTH ----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        mobile = request.form.get('mobile')
        email = request.form.get('email')
        password = request.form.get('password')
        shop_name = request.form.get('shop_name')
        dl_number = request.form.get('dl_number')
        address = request.form.get('address')

        existing = Customer.query.filter(
            (Customer.mobile == mobile) | (Customer.email == email)
        ).first()
        if existing:
            flash("Account already exists. Please login.", "warning")
            return redirect(url_for('login'))

        customer = Customer(
            shop_name=shop_name, dl_number=dl_number, mobile=mobile,
            email=email, address=address,
            password_hash=generate_password_hash(password),
            profile_complete=True
        )
        db.session.add(customer)
        db.session.commit()

        send_email("New Customer Registered - SWASTIK PHARMA",
                    f"Shop Name: {shop_name}\nDL Number: {dl_number}\nMobile: {mobile}\n"
                    f"Email: {email}\nAddress: {address}")

        session['customer_id'] = customer.id
        flash("WELCOME TO SWASTIK PHARMA", "success")
        return redirect(url_for('home'))

    return render_template('signup.html', business=BUSINESS_INFO)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')
        customer = Customer.query.filter(
            (Customer.mobile == identifier) | (Customer.email == identifier)
        ).first()
        if customer and check_password_hash(customer.password_hash, password):
            session['customer_id'] = customer.id
            flash("WELCOME TO SWASTIK PHARMA", "success")
            return redirect(url_for('home'))
        flash("Invalid credentials", "danger")
    return render_template('login.html', business=BUSINESS_INFO)

@app.route('/logout')
def logout():
    session.pop('customer_id', None)
    return redirect(url_for('home'))

# ---------------- ROUTES: ADMIN ----------------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            flash("WELCOME TO SWASTIK PHARMA (Admin)", "success")
            return redirect(url_for('admin_dashboard'))
        flash("Wrong password", "danger")
    return render_template('admin_login.html', business=BUSINESS_INFO)

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('home'))

def admin_required():
    return session.get('is_admin', False)

@app.route('/admin/dashboard')
def admin_dashboard():
    if not admin_required():
        return redirect(url_for('admin_login'))
    total_orders = Order.query.count()
    orders = Order.query.order_by(Order.created_at.desc()).limit(50).all()
    products = Product.query.all()
    return render_template('admin_dashboard.html', business=BUSINESS_INFO,
                            total_orders=total_orders, orders=orders, products=products)

@app.route('/admin/product/add', methods=['GET', 'POST'])
def admin_add_product():
    if not admin_required():
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        image_file = request.files.get('image')
        image_filename = "default.png"
        if image_file and image_file.filename:
            image_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        product = Product(
            name=request.form.get('name'),
            salt=request.form.get('salt'),
            brand=request.form.get('brand'),
            category=request.form.get('category'),
            mrp=float(request.form.get('mrp') or 0),
            ptr=float(request.form.get('ptr') or 0),
            image=image_filename,
            is_new='is_new' in request.form,
            is_top='is_top' in request.form,
            is_offer='is_offer' in request.form,
            offer_text=request.form.get('offer_text', '')
        )
        db.session.add(product)
        db.session.commit()
        flash("Product added successfully", "success")
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_add_product.html', business=BUSINESS_INFO, categories=CATEGORIES)

@app.route('/admin/product/edit/<int:product_id>', methods=['GET', 'POST'])
def admin_edit_product(product_id):
    if not admin_required():
        return redirect(url_for('admin_login'))
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.salt = request.form.get('salt')
        product.brand = request.form.get('brand')
        product.category = request.form.get('category')
        product.mrp = float(request.form.get('mrp') or 0)
        product.ptr = float(request.form.get('ptr') or 0)
        product.is_new = 'is_new' in request.form
        product.is_top = 'is_top' in request.form
        product.is_offer = 'is_offer' in request.form
        product.offer_text = request.form.get('offer_text', '')

        image_file = request.files.get('image')
        if image_file and image_file.filename:
            image_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
            product.image = image_filename

        db.session.commit()
        flash("Product updated", "success")
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_edit_product.html', product=product,
                            business=BUSINESS_INFO, categories=CATEGORIES)

@app.route('/admin/product/delete/<int:product_id>')
def admin_delete_product(product_id):
    if not admin_required():
        return redirect(url_for('admin_login'))
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted", "success")
    return redirect(url_for('admin_dashboard'))

# ---------------- INIT ----------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=False)
