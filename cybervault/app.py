from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cybervault.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'customer_login'

# ----------------------------- DATABASE MODELS -----------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    role = db.Column(db.String(20), default='buyer')
    balance = db.Column(db.Float, default=0.0)
    business_name = db.Column(db.String(100))
    specialty = db.Column(db.String(50))
    status = db.Column(db.String(20), default='active')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    market_price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50))
    stock = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String(200))
    description = db.Column(db.Text)
    vendor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ratings = db.Column(db.String(200), default='[]')
    sold_today = db.Column(db.Integer, default=0)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product', backref='cart_items')

class Order(db.Model):
    id = db.Column(db.String(20), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.Column(db.Text)

class Repair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    device = db.Column(db.String(100))
    issue = db.Column(db.Text)
    assigned_technician_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Delivery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(20))
    agent_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='assigned')
    completed_at = db.Column(db.DateTime)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ----------------------------- CUSTOMER ROUTES -----------------------------
@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        user = User(name=name, email=email, phone=phone, role='buyer')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please login.', 'success')
        return redirect(url_for('customer_login'))
    return render_template('register.html')

@app.route('/customer/login', methods=['GET', 'POST'])
def customer_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.role == 'buyer' and user.status == 'active':
            login_user(user)
            return redirect(url_for('customer_dashboard'))
        flash('Invalid credentials or not a buyer account', 'danger')
    return render_template('customer_login.html')

@app.route('/customer/dashboard')
@login_required
def customer_dashboard():
    if current_user.role != 'buyer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    products = Product.query.all()
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    return render_template('customer_dashboard.html', products=products, cart_items=cart_items)

@app.route('/add-to-cart/<int:product_id>')
@login_required
def add_to_cart(product_id):
    if current_user.role != 'buyer':
        flash('Only customers can add to cart', 'danger')
        return redirect(url_for('index'))
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=1)
        db.session.add(cart_item)
    db.session.commit()
    flash('Product added to cart', 'success')
    return redirect(url_for('customer_dashboard'))

@app.route('/remove-from-cart/<int:item_id>')
@login_required
def remove_from_cart(item_id):
    item = db.session.get(CartItem, item_id)
    if item and item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('Item removed', 'success')
    return redirect(url_for('customer_dashboard'))

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    if current_user.role != 'buyer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Cart is empty', 'danger')
        return redirect(url_for('customer_dashboard'))
    total = 0
    items_list = []
    for item in cart_items:
        product = item.product
        if product.stock < item.quantity:
            flash(f'Not enough stock for {product.name}', 'danger')
            return redirect(url_for('customer_dashboard'))
        product.stock -= item.quantity
        total += product.price * item.quantity
        items_list.append({'id': product.id, 'name': product.name, 'price': product.price, 'quantity': item.quantity})
        db.session.delete(item)
    order_id = 'ORD' + str(int(datetime.utcnow().timestamp()))
    order = Order(id=order_id, user_id=current_user.id, total=total, items=json.dumps(items_list))
    db.session.add(order)
    db.session.commit()
    flash(f'Order placed! Order ID: {order_id}', 'success')
    return redirect(url_for('customer_dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ----------------------------- MANAGEMENT LOGIN -----------------------------
@app.route('/management/login', methods=['GET', 'POST'])
def management_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.role != 'buyer' and user.status == 'active':
            login_user(user)
            if user.role == 'vendor':
                return redirect(url_for('vendor_dashboard'))
            elif user.role == 'technician':
                return redirect(url_for('technician_dashboard'))
            elif user.role == 'agent':
                return redirect(url_for('agent_dashboard'))
            elif user.role == 'installer':
                return redirect(url_for('installer_dashboard'))
            elif user.role == 'manager':
                return redirect(url_for('manager_dashboard'))
            elif user.role == 'superadmin':
                return redirect(url_for('superadmin_dashboard'))
        flash('Invalid credentials or not a management account', 'danger')
    return render_template('management_login.html')

# ----------------------------- VENDOR DASHBOARD -----------------------------
@app.route('/vendor/dashboard')
@login_required
def vendor_dashboard():
    if current_user.role != 'vendor':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    products = Product.query.filter_by(vendor_id=current_user.id).all()
    return render_template('vendor_dashboard.html', products=products)

@app.route('/vendor/add-product', methods=['POST'])
@login_required
def add_product():
    if current_user.role != 'vendor':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    name = request.form['name']
    price = float(request.form['price'])
    market_price = float(request.form['market_price'])
    category = request.form['category']
    stock = int(request.form['stock'])
    image_url = request.form['image_url']
    description = request.form['description']
    product = Product(name=name, price=price, market_price=market_price, category=category,
                     stock=stock, image_url=image_url, description=description, vendor_id=current_user.id)
    db.session.add(product)
    db.session.commit()
    flash('Product added', 'success')
    return redirect(url_for('vendor_dashboard'))

@app.route('/vendor/delete-product/<int:product_id>')
@login_required
def delete_product(product_id):
    if current_user.role != 'vendor':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    product = db.session.get(Product, product_id)
    if product and product.vendor_id == current_user.id:
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted', 'success')
    return redirect(url_for('vendor_dashboard'))

# ----------------------------- TECHNICIAN DASHBOARD -----------------------------
@app.route('/technician/dashboard')
@login_required
def technician_dashboard():
    if current_user.role != 'technician':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    repairs = Repair.query.filter_by(assigned_technician_id=current_user.id).all()
    return render_template('technician_dashboard.html', repairs=repairs)

# ----------------------------- AGENT DASHBOARD -----------------------------
@app.route('/agent/dashboard')
@login_required
def agent_dashboard():
    if current_user.role != 'agent':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    deliveries = Delivery.query.filter_by(agent_id=current_user.id).all()
    return render_template('agent_dashboard.html', deliveries=deliveries)

# ----------------------------- INSTALLER DASHBOARD -----------------------------
@app.route('/installer/dashboard')
@login_required
def installer_dashboard():
    if current_user.role != 'installer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    return render_template('installer_dashboard.html')

# ----------------------------- MANAGER DASHBOARD -----------------------------
@app.route('/manager/dashboard')
@login_required
def manager_dashboard():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    vendors = User.query.filter_by(role='vendor').all()
    total_sales = db.session.query(db.func.sum(Order.total)).scalar() or 0
    return render_template('manager_dashboard.html', vendors=vendors, total_sales=total_sales)

# ----------------------------- SUPERADMIN DASHBOARD -----------------------------
@app.route('/superadmin/dashboard')
@login_required
def superadmin_dashboard():
    if current_user.role != 'superadmin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    users = User.query.all()
    products = Product.query.all()
    orders = Order.query.all()
    return render_template('superadmin_dashboard.html', users=users, products=products, orders=orders)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create default superadmin if none exists
        if not User.query.filter_by(role='superadmin').first():
            admin = User(
                name='Maxwell',
                email='maxwell@cybervault.ug',
                phone='0708725402',
                role='superadmin',
                status='active'
            )
            admin.set_password('amitra734')
            db.session.add(admin)
            db.session.commit()
        # Create a sample product if none exists
        if not Product.query.first():
            sample = Product(
                name='Samsung Galaxy A54',
                price=1250000,
                market_price=1650000,
                category='Smartphones',
                stock=25,
                image_url='https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=400',
                description='6.4" display, 50MP camera'
            )
            db.session.add(sample)
            db.session.commit()
    app.run(debug=True)