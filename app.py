import os
import json
import io
import math
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, redirect, url_for, flash, request, session, send_file, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

if os.environ.get('RENDER'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/cybervault.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cybervault.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'customer_login'

# ----------------------------- MODELS -----------------------------
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class PlatformSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True, default=1)
    vendor_commission = db.Column(db.Float, default=0.10)
    agent_base_salary = db.Column(db.Float, default=300000)
    delivery_rate_per_km = db.Column(db.Float, default=1000)
    free_delivery_km = db.Column(db.Integer, default=5)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    market_price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50))
    stock = db.Column(db.Integer, default=0)
    image_filename = db.Column(db.String(200))
    description = db.Column(db.Text)
    vendor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ratings = db.Column(db.String(200), default='[]')
    sold_today = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product', backref='cart_items')

class Wishlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))

class Order(db.Model):
    id = db.Column(db.String(20), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    total = db.Column(db.Float, nullable=False)
    deposit_paid = db.Column(db.Float, default=0.0)
    balance = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.Column(db.Text)
    delivery_address = db.Column(db.String(200))
    customer_lat = db.Column(db.Float)
    customer_lng = db.Column(db.Float)
    transport_fee = db.Column(db.Float, default=0.0)

class Repair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    device = db.Column(db.String(100))
    issue = db.Column(db.Text)
    assigned_technician_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='pending')
    quote = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DeliveryAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(20), db.ForeignKey('order.id'))
    agent_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='assigned')
    distance_km = db.Column(db.Float, default=0.0)
    transport_fee = db.Column(db.Float, default=0.0)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    customer_confirmed_arrival = db.Column(db.Boolean, default=False)
    remaining_payment_confirmed = db.Column(db.Boolean, default=False)

class AgentLocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    lat = db.Column(db.Float, default=0.3136)
    lng = db.Column(db.Float, default=32.5811)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey('delivery_assignment.id'))
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    rating = db.Column(db.Integer)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Dispute(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='open')
    resolution = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(200))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ----------------------------- HELPER FUNCTIONS -----------------------------
def get_settings():
    s = PlatformSettings.query.first()
    if not s:
        s = PlatformSettings()
        db.session.add(s)
        db.session.commit()
    return s

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def assign_agent_for_order(order_id, customer_lat, customer_lng):
    agents = User.query.filter_by(role='agent', status='active').all()
    if not agents:
        return None
    best_agent = None
    best_dist = float('inf')
    for agent in agents:
        loc = AgentLocation.query.filter_by(agent_id=agent.id).first()
        if not loc:
            loc = AgentLocation(agent_id=agent.id, lat=0.3136, lng=32.5811)
            db.session.add(loc)
            db.session.commit()
        dist = haversine(loc.lat, loc.lng, customer_lat, customer_lng)
        if dist < best_dist:
            best_dist = dist
            best_agent = agent
    if best_agent:
        settings = get_settings()
        free_km = settings.free_delivery_km
        rate = settings.delivery_rate_per_km
        distance_km = max(0, best_dist - free_km)
        fee = distance_km * rate
        da = DeliveryAssignment(
            order_id=order_id,
            agent_id=best_agent.id,
            distance_km=distance_km,
            transport_fee=fee
        )
        db.session.add(da)
        db.session.commit()
        return da
    return None

# ----------------------------- ROUTES (Customer) -----------------------------
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
        flash('Invalid credentials', 'danger')
    return render_template('customer_login.html')

@app.route('/customer/dashboard')
@login_required
def customer_dashboard():
    if current_user.role != 'buyer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    products = Product.query.all()
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('customer_dashboard.html', products=products, cart_items=cart_items, orders=orders)

@app.route('/add-to-cart/<int:product_id>')
@login_required
def add_to_cart(product_id):
    if current_user.role != 'buyer':
        flash('Only customers can add to cart', 'danger')
        return redirect(url_for('index'))
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if item:
        item.quantity += 1
    else:
        item = CartItem(user_id=current_user.id, product_id=product_id, quantity=1)
        db.session.add(item)
    db.session.commit()
    flash('Added to cart', 'success')
    return redirect(url_for('customer_dashboard'))

@app.route('/remove-from-cart/<int:item_id>')
@login_required
def remove_from_cart(item_id):
    item = db.session.get(CartItem, item_id)
    if item and item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('Removed', 'success')
    return redirect(url_for('customer_dashboard'))

@app.route('/update-cart/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    item = db.session.get(CartItem, item_id)
    if item and item.user_id == current_user.id:
        new_qty = int(request.form['quantity'])
        if new_qty <= 0:
            db.session.delete(item)
        else:
            item.quantity = new_qty
        db.session.commit()
    return redirect(url_for('customer_dashboard'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    if current_user.role != 'buyer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Cart empty', 'danger')
        return redirect(url_for('customer_dashboard'))
    if request.method == 'POST':
        address = request.form['address']
        lat = float(request.form['lat'])
        lng = float(request.form['lng'])
        warehouse_lat = 0.3136
        warehouse_lng = 32.5811
        dist = haversine(warehouse_lat, warehouse_lng, lat, lng)
        settings = get_settings()
        free_km = settings.free_delivery_km
        chargeable = max(0, dist - free_km)
        transport_fee = chargeable * settings.delivery_rate_per_km
        product_total = sum(item.product.price * item.quantity for item in cart_items)
        deposit = product_total * 0.5
        balance = product_total - deposit
        total = product_total + transport_fee
        order_id = 'ORD' + str(int(datetime.utcnow().timestamp()))
        order = Order(
            id=order_id, user_id=current_user.id, total=total,
            deposit_paid=0, balance=balance,
            status='pending_deposit', delivery_address=address,
            customer_lat=lat, customer_lng=lng, transport_fee=transport_fee,
            items=json.dumps([{'id': item.product.id, 'name': item.product.name, 'price': item.product.price, 'quantity': item.quantity} for item in cart_items])
        )
        db.session.add(order)
        for item in cart_items:
            product = item.product
            product.stock -= item.quantity
            db.session.delete(item)
        db.session.commit()
        order.deposit_paid = deposit
        order.status = 'deposit_paid'
        db.session.commit()
        da = assign_agent_for_order(order_id, lat, lng)
        if da:
            flash(f'Order placed! Deposit of UGX {deposit:.0f} paid. Balance UGX {balance:.0f} due on delivery. Agent assigned.', 'success')
        else:
            flash(f'Order placed! Deposit paid. No agent available yet – will assign soon.', 'warning')
        return redirect(url_for('customer_orders'))
    return render_template('checkout.html', cart_items=cart_items)

@app.route('/customer/orders')
@login_required
def customer_orders():
    if current_user.role != 'buyer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('customer_orders.html', orders=orders)

@app.route('/order/<order_id>')
@login_required
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and current_user.role not in ['manager','superadmin']:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    delivery = DeliveryAssignment.query.filter_by(order_id=order_id).first()
    agent = None
    if delivery:
        agent = User.query.get(delivery.agent_id)
    return render_template('order_detail.html', order=order, delivery=delivery, agent=agent)

@app.route('/order/<order_id>/chat')
@login_required
def order_chat(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    delivery = DeliveryAssignment.query.filter_by(order_id=order_id).first()
    if not delivery:
        flash('No delivery assigned yet', 'warning')
        return redirect(url_for('view_order', order_id=order_id))
    return render_template('order_chat.html', order=order, delivery=delivery)

@app.route('/api/chat/<int:delivery_id>', methods=['GET', 'POST'])
@login_required
def chat_api(delivery_id):
    delivery = DeliveryAssignment.query.get_or_404(delivery_id)
    order = Order.query.get(delivery.order_id)
    if not (current_user.id == order.user_id or current_user.id == delivery.agent_id):
        return jsonify({'error': 'Unauthorized'}), 403
    if request.method == 'POST':
        msg = request.json.get('message')
        if msg:
            chat = ChatMessage(delivery_id=delivery_id, sender_id=current_user.id, message=msg)
            db.session.add(chat)
            db.session.commit()
        return jsonify({'status': 'ok'})
    else:
        messages = ChatMessage.query.filter_by(delivery_id=delivery_id).order_by(ChatMessage.timestamp).all()
        return jsonify([{'sender': m.sender_id, 'message': m.message, 'timestamp': m.timestamp.isoformat()} for m in messages])

@app.route('/api/agent/location/<int:agent_id>')
@login_required
def agent_location(agent_id):
    if current_user.role == 'buyer':
        has_order = DeliveryAssignment.query.join(Order).filter(
            DeliveryAssignment.agent_id == agent_id,
            Order.user_id == current_user.id
        ).first()
        if not has_order:
            return jsonify({'error': 'Unauthorized'}), 403
    loc = AgentLocation.query.filter_by(agent_id=agent_id).first()
    if not loc:
        loc = AgentLocation(agent_id=agent_id, lat=0.3136, lng=32.5811)
        db.session.add(loc)
        db.session.commit()
    return jsonify({'lat': loc.lat, 'lng': loc.lng, 'updated_at': loc.updated_at.isoformat()})

@app.route('/api/agent/update-location', methods=['POST'])
@login_required
def update_agent_location():
    if current_user.role != 'agent':
        return jsonify({'error': 'Only agents can update location'}), 403
    data = request.json
    lat = data.get('lat')
    lng = data.get('lng')
    if lat is None or lng is None:
        return jsonify({'error': 'Missing coordinates'}), 400
    loc = AgentLocation.query.filter_by(agent_id=current_user.id).first()
    if not loc:
        loc = AgentLocation(agent_id=current_user.id)
        db.session.add(loc)
    loc.lat = lat
    loc.lng = lng
    loc.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'ok'})

@app.route('/order/<order_id>/confirm-arrival', methods=['POST'])
@login_required
def confirm_arrival(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    delivery = DeliveryAssignment.query.filter_by(order_id=order_id).first()
    if not delivery:
        flash('No delivery assignment', 'danger')
        return redirect(url_for('view_order', order_id=order_id))
    if delivery.customer_confirmed_arrival:
        flash('Already confirmed', 'info')
        return redirect(url_for('view_order', order_id=order_id))
    order.balance = 0
    order.status = 'delivered'
    delivery.customer_confirmed_arrival = True
    delivery.remaining_payment_confirmed = True
    delivery.status = 'delivered'
    db.session.commit()
    flash('Order delivered! Thank you.', 'success')
    return redirect(url_for('customer_orders'))

# ----------------------------- VENDOR ROUTES -----------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@app.route('/vendor/dashboard')
@login_required
def vendor_dashboard():
    if current_user.role != 'vendor':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    products = Product.query.filter_by(vendor_id=current_user.id).all()
    earnings = sum([p.price for p in products]) * get_settings().vendor_commission
    return render_template('vendor_dashboard.html', products=products, earnings=earnings)

@app.route('/vendor/add-product', methods=['POST'])
@login_required
def vendor_add_product():
    if current_user.role != 'vendor':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    name = request.form['name']
    price = float(request.form['price'])
    market_price = float(request.form['market_price'])
    category = request.form['category']
    stock = int(request.form['stock'])
    description = request.form['description']
    file = request.files.get('image')
    filename = None
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        name_parts = filename.rsplit('.', 1)
        filename = f"{datetime.utcnow().timestamp()}_{name_parts[0]}.{name_parts[1]}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    product = Product(
        name=name, price=price, market_price=market_price, category=category,
        stock=stock, image_filename=filename, description=description, vendor_id=current_user.id
    )
    db.session.add(product)
    db.session.commit()
    flash('Product added', 'success')
    return redirect(url_for('vendor_dashboard'))

@app.route('/vendor/delete-product/<int:product_id>')
@login_required
def vendor_delete_product(product_id):
    if current_user.role != 'vendor':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    product = db.session.get(Product, product_id)
    if product and product.vendor_id == current_user.id:
        if product.image_filename:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], product.image_filename))
            except:
                pass
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted', 'success')
    return redirect(url_for('vendor_dashboard'))

@app.route('/vendor/workers')
@login_required
def vendor_workers():
    if current_user.role != 'vendor':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    workers = User.query.filter(User.role.in_(['technician', 'agent', 'installer'])).all()
    return render_template('vendor_workers.html', workers=workers)

# ----------------------------- TECHNICIAN ROUTES -----------------------------
@app.route('/technician/dashboard')
@login_required
def technician_dashboard():
    if current_user.role != 'technician':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    repairs = Repair.query.filter_by(assigned_technician_id=current_user.id).all()
    earnings = sum([r.quote or 0 for r in repairs if r.status == 'completed'])
    return render_template('technician_dashboard.html', repairs=repairs, earnings=earnings)

@app.route('/technician/update-repair/<int:repair_id>', methods=['POST'])
@login_required
def technician_update_repair(repair_id):
    if current_user.role != 'technician':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    repair = db.session.get(Repair, repair_id)
    if repair and repair.assigned_technician_id == current_user.id:
        repair.status = request.form['status']
        db.session.commit()
        flash('Repair updated', 'success')
    return redirect(url_for('technician_dashboard'))

# ----------------------------- AGENT ROUTES -----------------------------
@app.route('/agent/dashboard')
@login_required
def agent_dashboard():
    if current_user.role != 'agent':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    deliveries = DeliveryAssignment.query.filter_by(agent_id=current_user.id).all()
    points = min(len([d for d in deliveries if d.status == 'delivered']), 10)
    settings = get_settings()
    salary = int((points / 10) * settings.agent_base_salary)
    return render_template('agent_dashboard.html', deliveries=deliveries, points=points, salary=salary)

@app.route('/agent/update-delivery/<int:delivery_id>', methods=['POST'])
@login_required
def agent_update_delivery(delivery_id):
    if current_user.role != 'agent':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    delivery = db.session.get(DeliveryAssignment, delivery_id)
    if delivery and delivery.agent_id == current_user.id:
        new_status = request.form['status']
        delivery.status = new_status
        if new_status == 'delivered':
            delivery.completed_at = datetime.utcnow()
        db.session.commit()
        flash('Delivery updated', 'success')
    return redirect(url_for('agent_dashboard'))

@app.route('/agent/withdraw', methods=['POST'])
@login_required
def agent_withdraw():
    if current_user.role != 'agent':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    amount = float(request.form['amount'])
    if amount > current_user.balance:
        flash('Insufficient balance', 'danger')
        return redirect(url_for('agent_dashboard'))
    current_user.balance -= amount
    db.session.commit()
    flash('Withdrawal request submitted', 'success')
    return redirect(url_for('agent_dashboard'))

# ----------------------------- INSTALLER ROUTES -----------------------------
@app.route('/installer/dashboard')
@login_required
def installer_dashboard():
    if current_user.role != 'installer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    return render_template('installer_dashboard.html')

# ----------------------------- MANAGER ROUTES -----------------------------
@app.route('/manager/dashboard')
@login_required
def manager_dashboard():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    deliveries = DeliveryAssignment.query.all()
    agents = User.query.filter_by(role='agent').all()
    return render_template('manager_dashboard.html', deliveries=deliveries, agents=agents)

@app.route('/manager/reassign-delivery/<int:delivery_id>', methods=['POST'])
@login_required
def reassign_delivery(delivery_id):
    if current_user.role != 'manager':
        return jsonify({'error': 'Unauthorized'}), 403
    new_agent_id = request.form['agent_id']
    delivery = DeliveryAssignment.query.get(delivery_id)
    if not delivery:
        flash('Delivery not found', 'danger')
        return redirect(url_for('manager_dashboard'))
    old_agent_id = delivery.agent_id
    delivery.agent_id = new_agent_id
    db.session.commit()
    flash(f'Reassigned from agent {old_agent_id} to {new_agent_id}', 'success')
    return redirect(url_for('manager_dashboard'))

# ----------------------------- SUPERADMIN ROUTES -----------------------------
@app.route('/superadmin/dashboard')
@login_required
def superadmin_dashboard():
    if current_user.role != 'superadmin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    users = User.query.all()
    products = Product.query.all()
    orders = Order.query.all()
    settings = get_settings()
    return render_template('superadmin_dashboard.html', users=users, products=products, orders=orders, settings=settings)

@app.route('/superadmin/create-user', methods=['POST'])
@login_required
def superadmin_create_user():
    if current_user.role != 'superadmin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    name = request.form['name']
    email = request.form['email']
    phone = request.form['phone']
    role = request.form['role']
    password = request.form['password']
    if User.query.filter_by(email=email).first():
        flash('Email already exists', 'danger')
        return redirect(url_for('superadmin_dashboard'))
    user = User(name=name, email=email, phone=phone, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash('User created', 'success')
    return redirect(url_for('superadmin_dashboard'))

@app.route('/superadmin/delete-user/<int:user_id>')
@login_required
def superadmin_delete_user(user_id):
    if current_user.role != 'superadmin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    user = db.session.get(User, user_id)
    if user and user.id != current_user.id:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted', 'success')
    return redirect(url_for('superadmin_dashboard'))

@app.route('/superadmin/settings', methods=['POST'])
@login_required
def superadmin_settings():
    if current_user.role != 'superadmin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    settings = get_settings()
    settings.vendor_commission = float(request.form['vendor_commission']) / 100
    settings.agent_base_salary = float(request.form['agent_base_salary'])
    db.session.commit()
    flash('Settings updated', 'success')
    return redirect(url_for('superadmin_dashboard'))

@app.route('/superadmin/backup')
@login_required
def superadmin_backup():
    if current_user.role != 'superadmin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    data = {
        'users': [{'id': u.id, 'email': u.email, 'name': u.name, 'role': u.role} for u in User.query.all()],
        'products': [{'id': p.id, 'name': p.name, 'price': p.price} for p in Product.query.all()],
        'orders': [{'id': o.id, 'total': o.total, 'status': o.status} for o in Order.query.all()]
    }
    json_str = json.dumps(data, indent=2)
    return send_file(io.BytesIO(json_str.encode()), as_attachment=True, download_name='cybervault_backup.json', mimetype='application/json')

@app.route('/superadmin/restore', methods=['POST'])
@login_required
def superadmin_restore():
    if current_user.role != 'superadmin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    file = request.files.get('backup_file')
    if not file:
        flash('No file uploaded', 'danger')
        return redirect(url_for('superadmin_dashboard'))
    flash('Restore feature requires manual merge for security', 'warning')
    return redirect(url_for('superadmin_dashboard'))

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
        flash('Invalid credentials', 'danger')
    return render_template('management_login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ----------------------------- STATIC FILE SERVING -----------------------------
# This is the only route for static uploads – duplicate removed
@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ----------------------------- TEMPLATE WRITER -----------------------------
def ensure_templates():
    os.makedirs('templates', exist_ok=True)
    templates = {
        'base.html': '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CyberVault – Uganda's Marketplace</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <style>
        body { background: #0a0a0a; color: #fff; font-family: 'Segoe UI', sans-serif; }
        .navbar { background: rgba(10,10,10,0.9); border-bottom: 2px solid #D4AF37; }
        .navbar-brand { color: #D4AF37; font-weight: bold; font-size: 1.5rem; }
        .btn-gold { background: #D4AF37; color: #0a0a0a; border: none; }
        .btn-gold:hover { background: #b8960c; }
        .card { background: rgba(26,26,46,0.8); backdrop-filter: blur(10px); border: 1px solid rgba(212,175,55,0.3); border-radius: 15px; }
        .card:hover { border-color: #D4AF37; transform: translateY(-3px); transition: 0.3s; }
        footer { text-align: center; padding: 20px; color: #aaa; margin-top: 50px; border-top: 1px solid #333; }
        .text-gold { color: #D4AF37; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">CYBER<span style="color:white;">VAULT</span></a>
            <div class="ms-auto">
                {% if current_user.is_authenticated %}
                    <span class="text-gold me-2">{{ current_user.name }}</span>
                    <a href="{{ url_for('logout') }}" class="btn btn-outline-light btn-sm">Logout</a>
                {% else %}
                    <a href="{{ url_for('customer_login') }}" class="btn btn-outline-light btn-sm">Customer Login</a>
                    <a href="{{ url_for('register') }}" class="btn btn-gold btn-sm ms-2">Sign Up</a>
                    <a href="{{ url_for('management_login') }}" class="btn btn-outline-gold btn-sm ms-2">Mgmt</a>
                {% endif %}
            </div>
        </div>
    </nav>
    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endwith %}
        {% block content %}{% endblock %}
    </div>
    <footer>&copy; 2026 CyberVault – Uganda's Trusted Marketplace</footer>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>''',
        'index.html': '''{% extends "base.html" %}
{% block content %}
<div class="row mb-4">
    <div class="col-md-4">
        <input type="text" id="searchInput" class="form-control" placeholder="Search products..." onkeyup="filterProducts()">
    </div>
    <div class="col-md-3">
        <select id="categorySelect" class="form-select" onchange="filterProducts()">
            <option value="all">All Categories</option>
            <option value="Smartphones">Smartphones</option>
            <option value="Laptops">Laptops</option>
            <option value="eBooks">eBooks</option>
            <option value="Accessories">Accessories</option>
        </select>
    </div>
</div>
<div id="productsGrid" class="row">
    {% for product in products %}
    <div class="col-md-4 col-lg-3 mb-4 product-item" data-name="{{ product.name|lower }}" data-category="{{ product.category }}">
        <div class="card h-100 p-3">
            {% if product.image_filename %}
                <img src="{{ url_for('uploaded_file', filename=product.image_filename) }}" class="card-img-top" style="height: 180px; object-fit: cover;">
            {% else %}
                <img src="https://via.placeholder.com/300" class="card-img-top" style="height: 180px; object-fit: cover;">
            {% endif %}
            <div class="card-body">
                <h5 class="card-title">{{ product.name }}</h5>
                <div class="text-gold fw-bold">UGX {{ product.price|int }}</div>
                <div class="text-muted"><del>UGX {{ product.market_price|int }}</del></div>
                {% if current_user.is_authenticated and current_user.role == 'buyer' %}
                    <a href="{{ url_for('add_to_cart', product_id=product.id) }}" class="btn btn-gold w-100 mt-2">Add to Cart</a>
                {% else %}
                    <a href="{{ url_for('customer_login') }}" class="btn btn-gold w-100 mt-2">Login to Buy</a>
                {% endif %}
            </div>
        </div>
    </div>
    {% endfor %}
</div>
<script>
function filterProducts() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    const category = document.getElementById('categorySelect').value;
    const items = document.querySelectorAll('.product-item');
    items.forEach(item => {
        const name = item.dataset.name;
        const cat = item.dataset.category;
        let match = true;
        if (search && !name.includes(search)) match = false;
        if (category !== 'all' && cat !== category) match = false;
        item.style.display = match ? '' : 'none';
    });
}
</script>
{% endblock %}''',
        'register.html': '''{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card p-4">
            <h2 class="text-center mb-4">Sign Up</h2>
            <form method="POST">
                <div class="mb-3"><label>Full Name</label><input type="text" name="name" class="form-control" required></div>
                <div class="mb-3"><label>Email</label><input type="email" name="email" class="form-control" required></div>
                <div class="mb-3"><label>Phone</label><input type="tel" name="phone" class="form-control" required></div>
                <div class="mb-3"><label>Password</label><input type="password" name="password" class="form-control" required></div>
                <button type="submit" class="btn btn-gold w-100">Sign Up</button>
            </form>
            <p class="mt-3 text-center">Already have an account? <a href="{{ url_for('customer_login') }}">Login</a></p>
        </div>
    </div>
</div>
{% endblock %}''',
        'customer_login.html': '''{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card p-4">
            <h2 class="text-center mb-4">Customer Login</h2>
            <form method="POST">
                <div class="mb-3"><label>Email</label><input type="email" name="email" class="form-control" required></div>
                <div class="mb-3"><label>Password</label><input type="password" name="password" class="form-control" required></div>
                <button type="submit" class="btn btn-gold w-100">Login</button>
            </form>
            <p class="mt-3 text-center">New? <a href="{{ url_for('register') }}">Sign Up</a></p>
        </div>
    </div>
</div>
{% endblock %}''',
        'customer_dashboard.html': '''{% extends "base.html" %}
{% block content %}
<h2 class="mb-4">🛍️ My Dashboard</h2>
<div class="row">
    <div class="col-md-8">
        <div class="card p-3 mb-4">
            <h4>Your Cart</h4>
            {% if cart_items %}
                <table class="table table-dark">
                    <thead><tr><th>Product</th><th>Price</th><th>Qty</th><th>Total</th><th></th></tr></thead>
                    <tbody>
                    {% set ns = namespace(total=0) %}
                    {% for item in cart_items %}
                        {% set item_total = item.product.price * item.quantity %}
                        {% set ns.total = ns.total + item_total %}
                        <tr>
                            <td>{{ item.product.name }}</td>
                            <td>UGX {{ item.product.price|int }}</td>
                            <td><form method="POST" action="{{ url_for('update_cart', item_id=item.id) }}" class="d-inline"><input type="number" name="quantity" value="{{ item.quantity }}" style="width:60px" min="1"><button type="submit" class="btn btn-sm btn-secondary">Update</button></form></td>
                            <td>UGX {{ item_total|int }}</td>
                            <td><a href="{{ url_for('remove_from_cart', item_id=item.id) }}" class="btn btn-sm btn-danger">Remove</a></td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>
                <div class="d-flex justify-content-between">
                    <h5>Total: UGX {{ ns.total|int }}</h5>
                    <a href="{{ url_for('checkout') }}" class="btn btn-gold">Proceed to Checkout</a>
                </div>
            {% else %}
                <p>Your cart is empty.</p>
            {% endif %}
        </div>
        <div class="card p-3 mb-4">
            <h4>Quick Actions</h4>
            <a href="{{ url_for('customer_orders') }}" class="btn btn-outline-gold w-100 mb-2">My Orders</a>
            <a href="{{ url_for('wishlist_page') }}" class="btn btn-outline-gold w-100 mb-2">My Wishlist</a>
            <a href="{{ url_for('repair_request') }}" class="btn btn-outline-gold w-100 mb-2">Request Repair</a>
            <a href="{{ url_for('my_repairs') }}" class="btn btn-outline-gold w-100 mb-2">My Repairs</a>
            <a href="{{ url_for('referral_link') }}" class="btn btn-outline-gold w-100">Refer a Friend</a>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card p-3">
            <h4>Recently Viewed</h4>
            {% for p in recent_products %}
                <div class="mb-2"><a href="{{ url_for('index') }}" class="text-decoration-none">{{ p.name }}</a></div>
            {% else %}
                <p>None</p>
            {% endfor %}
        </div>
    </div>
</div>
<h3 class="mt-5">🔥 Recommended for You</h3>
<div class="row">
    {% for product in products[:4] %}
    <div class="col-md-3 mb-3">
        <div class="card h-100 p-2">
            {% if product.image_filename %}
                <img src="{{ url_for('uploaded_file', filename=product.image_filename) }}" class="card-img-top" style="height: 120px; object-fit: cover;">
            {% else %}
                <img src="https://via.placeholder.com/200" class="card-img-top">
            {% endif %}
            <div class="card-body p-2">
                <h6>{{ product.name }}</h6>
                <div class="text-gold fw-bold">UGX {{ product.price|int }}</div>
                <a href="{{ url_for('add_to_cart', product_id=product.id) }}" class="btn btn-sm btn-gold w-100 mt-2">Add to Cart</a>
            </div>
        </div>
    </div>
    {% endfor %}
</div>
{% endblock %}''',
        'customer_orders.html': '''{% extends "base.html" %}
{% block content %}
<h2>My Orders</h2>
{% for order in orders %}
<div class="card mb-3 p-3">
    <div><strong>Order #{{ order.id }}</strong> - {{ order.created_at.strftime('%Y-%m-%d %H:%M') }} - Status: {{ order.status }}</div>
    <div>Total: UGX {{ order.total|int }}</div>
    <a href="{{ url_for('view_order', order_id=order.id) }}" class="btn btn-sm btn-outline-gold">View Details</a>
</div>
{% else %}
<p>No orders yet.</p>
{% endfor %}
{% endblock %}''',
        'checkout.html': '''{% extends "base.html" %}
{% block content %}
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<h2>Checkout</h2>
<form method="POST">
    <div class="mb-3"><label>Delivery Address</label><input type="text" name="address" class="form-control" required></div>
    <div class="mb-3"><label>Pick your delivery location on the map</label><div id="map" style="height: 300px;"></div></div>
    <input type="hidden" id="lat" name="lat">
    <input type="hidden" id="lng" name="lng">
    <div class="card p-3 mb-3">
        <h4>Order Summary</h4>
        {% for item in cart_items %}
            <div>{{ item.product.name }} x{{ item.quantity }} = UGX {{ (item.product.price * item.quantity)|int }}</div>
        {% endfor %}
        <hr>
        <strong>Subtotal: UGX {{ cart_items|sum(attribute='product.price')|int }}</strong><br>
        <strong>Delivery fee: will be calculated after location selection</strong><br>
        <strong>Deposit (50%): will be calculated</strong><br>
        <strong>Balance (50%): will be calculated</strong>
    </div>
    <button type="submit" class="btn btn-gold">Place Order (Pay 50% Deposit)</button>
</form>
<script>
    var map = L.map('map').setView([0.3136, 32.5811], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    var marker;
    map.on('click', function(e) {
        if (marker) map.removeLayer(marker);
        marker = L.marker(e.latlng).addTo(map);
        document.getElementById('lat').value = e.latlng.lat;
        document.getElementById('lng').value = e.latlng.lng;
    });
</script>
{% endblock %}''',
        'order_detail.html': '''{% extends "base.html" %}
{% block content %}
<h2>Order #{{ order.id }}</h2>
<p>Status: {{ order.status }}</p>
<p>Delivery address: {{ order.delivery_address }}</p>
<p>Transport fee: UGX {{ order.transport_fee|int }}</p>
<p>Deposit paid: UGX {{ order.deposit_paid|int }}</p>
<p>Balance due: UGX {{ order.balance|int }}</p>
{% if delivery %}
    <p>Agent: {{ agent.name }} ({{ agent.phone }})</p>
    <div id="agentMap" style="height: 300px;"></div>
    <a href="{{ url_for('order_chat', order_id=order.id) }}" class="btn btn-gold">Chat with Agent</a>
    {% if not delivery.customer_confirmed_arrival %}
        <form method="POST" action="{{ url_for('confirm_arrival', order_id=order.id) }}">
            <button type="submit" class="btn btn-success">Confirm Arrival & Pay Balance</button>
        </form>
    {% endif %}
{% else %}
    <p>No delivery assigned yet.</p>
{% endif %}
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
    var map = L.map('agentMap').setView([0.3136, 32.5811], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    function updateAgentLocation() {
        fetch('/api/agent/location/{{ delivery.agent_id if delivery else 0 }}')
            .then(r => r.json())
            .then(data => {
                if (data.lat && data.lng) {
                    if (window.agentMarker) map.removeLayer(window.agentMarker);
                    window.agentMarker = L.marker([data.lat, data.lng]).addTo(map).bindPopup('Agent').openPopup();
                    map.setView([data.lat, data.lng], 13);
                }
            });
    }
    updateAgentLocation();
    setInterval(updateAgentLocation, 5000);
</script>
{% endblock %}''',
        'order_chat.html': '''{% extends "base.html" %}
{% block content %}
<h2>Chat with Delivery Agent</h2>
<div id="chatMessages" style="height: 400px; overflow-y: auto; background: #1a1a2e; border-radius: 10px; padding: 10px;"></div>
<input type="text" id="messageInput" class="form-control mt-2" placeholder="Type your message...">
<button id="sendBtn" class="btn btn-gold mt-2">Send</button>
<script>
    const deliveryId = {{ delivery.id }};
    function loadMessages() {
        fetch(`/api/chat/${deliveryId}`)
            .then(r => r.json())
            .then(messages => {
                const container = document.getElementById('chatMessages');
                container.innerHTML = '';
                messages.forEach(m => {
                    const div = document.createElement('div');
                    div.textContent = `${m.sender}: ${m.message}`;
                    container.appendChild(div);
                });
                container.scrollTop = container.scrollHeight;
            });
    }
    document.getElementById('sendBtn').onclick = () => {
        const msg = document.getElementById('messageInput').value;
        if (!msg) return;
        fetch(`/api/chat/${deliveryId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: msg})
        }).then(() => {
            document.getElementById('messageInput').value = '';
            loadMessages();
        });
    };
    loadMessages();
    setInterval(loadMessages, 2000);
</script>
{% endblock %}''',
        'management_login.html': '''{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card p-4">
            <h2 class="text-center mb-4">Management Login</h2>
            <form method="POST">
                <div class="mb-3"><label>Email</label><input type="email" name="email" class="form-control" required></div>
                <div class="mb-3"><label>Password</label><input type="password" name="password" class="form-control" required></div>
                <button type="submit" class="btn btn-gold w-100">Login</button>
            </form>
        </div>
    </div>
</div>
{% endblock %}''',
        'vendor_dashboard.html': '''{% extends "base.html" %}
{% block content %}
<h2>Vendor Dashboard</h2>
<p>Welcome, {{ current_user.business_name or current_user.name }}</p>
<div class="row">
    <div class="col-md-6">
        <div class="card p-3 mb-3">
            <h4>Your Products</h4>
            {% for product in products %}
            <div class="d-flex justify-content-between align-items-center border-bottom py-2">
                <div>
                    <strong>{{ product.name }}</strong> - UGX {{ product.price|int }} (Stock: {{ product.stock }})
                    {% if product.image_filename %}
                        <br><img src="{{ url_for('uploaded_file', filename=product.image_filename) }}" style="height: 50px;">
                    {% endif %}
                </div>
                <a href="{{ url_for('vendor_delete_product', product_id=product.id) }}" class="btn btn-sm btn-danger">Delete</a>
            </div>
            {% else %}
            <p>No products yet.</p>
            {% endfor %}
        </div>
    </div>
    <div class="col-md-6">
        <div class="card p-3">
            <h4>Add Product</h4>
            <form method="POST" action="{{ url_for('vendor_add_product') }}" enctype="multipart/form-data">
                <input type="text" name="name" class="form-control mb-2" placeholder="Name" required>
                <input type="number" name="price" class="form-control mb-2" placeholder="Price" required>
                <input type="number" name="market_price" class="form-control mb-2" placeholder="Market Price" required>
                <input type="text" name="category" class="form-control mb-2" placeholder="Category">
                <input type="number" name="stock" class="form-control mb-2" placeholder="Stock" required>
                <input type="file" name="image" class="form-control mb-2" accept="image/*">
                <textarea name="description" class="form-control mb-2" placeholder="Description"></textarea>
                <button type="submit" class="btn btn-gold w-100">Add Product</button>
            </form>
        </div>
    </div>
</div>
<div class="card p-3 mt-3">
    <h4>Stats</h4>
    <p>Total Products: {{ products|length }}</p>
    <p>Estimated Commission: UGX {{ earnings|int }}</p>
</div>
<a href="{{ url_for('vendor_workers') }}" class="btn btn-outline-gold mt-3">Manage Workers</a>
{% endblock %}''',
        'vendor_workers.html': '''{% extends "base.html" %}
{% block content %}
<h2>Manage Workers</h2>
<table class="table table-dark">
    <thead><tr><th>Name</th><th>Role</th><th>Email</th></tr></thead>
    <tbody>
    {% for w in workers %}
    <tr><td>{{ w.name }}</td><td>{{ w.role }}</td><td>{{ w.email }}</td></tr>
    {% endfor %}
    </tbody>
</table>
{% endblock %}''',
        'technician_dashboard.html': '''{% extends "base.html" %}
{% block content %}
<h2>Technician Dashboard</h2>
<p>Welcome, {{ current_user.name }}</p>
<h4>Assigned Repairs</h4>
{% for repair in repairs %}
<div class="card p-2 mb-2">
    <div>{{ repair.device }} - {{ repair.status }}</div>
    <form method="POST" action="{{ url_for('technician_update_repair', repair_id=repair.id) }}">
        <select name="status" class="form-select d-inline w-50">
            <option value="pending">Pending</option>
            <option value="diagnosing">Diagnosing</option>
            <option value="repairing">Repairing</option>
            <option value="completed">Completed</option>
        </select>
        <button type="submit" class="btn btn-sm btn-gold">Update</button>
    </form>
</div>
{% else %}
<p>No repairs assigned.</p>
{% endfor %}
<p><strong>Total earnings: UGX {{ earnings|int }}</strong></p>
{% endblock %}''',
        'agent_dashboard.html': '''{% extends "base.html" %}
{% block content %}
<h2>Delivery Agent Dashboard</h2>
<p>Welcome, {{ current_user.name }}</p>
<div class="card p-3 mb-3">
    <h4>Performance</h4>
    <p>Points: {{ points }}/10 &nbsp;&nbsp; Monthly Salary: UGX {{ salary|int }}</p>
    <p>Available Balance: UGX {{ current_user.balance|int }}</p>
    <form method="POST" action="{{ url_for('agent_withdraw') }}" class="d-inline">
        <input type="number" name="amount" placeholder="Amount" required>
        <button type="submit" class="btn btn-gold">Withdraw</button>
    </form>
</div>
<h4>Your Deliveries</h4>
{% for delivery in deliveries %}
<div class="card p-2 mb-2">
    <div>Order {{ delivery.order_id }} - Status: {{ delivery.status }}</div>
    <form method="POST" action="{{ url_for('agent_update_delivery', delivery_id=delivery.id) }}">
        <select name="status" class="form-select d-inline w-50">
            <option value="assigned">Assigned</option>
            <option value="picked_up">Picked Up</option>
            <option value="in_transit">In Transit</option>
            <option value="delivered">Delivered</option>
        </select>
        <button type="submit" class="btn btn-sm btn-gold">Update</button>
    </form>
</div>
{% else %}
<p>No deliveries assigned.</p>
{% endfor %}
{% endblock %}''',
        'installer_dashboard.html': '''{% extends "base.html" %}
{% block content %}
<h2>Installer Dashboard</h2>
<p>Installation requests will appear here.</p>
{% endblock %}''',
        'manager_dashboard.html': '''{% extends "base.html" %}
{% block content %}
<h2>Manager Dashboard</h2>
<div class="row">
    <div class="col-md-6">
        <h3>Active Deliveries</h3>
        <ul>
        {% for d in deliveries %}
            <li>Order {{ d.order_id }} – Agent {{ d.agent_id }} – Status {{ d.status }}</li>
        {% endfor %}
        </ul>
    </div>
    <div class="col-md-6">
        <h3>Reassign Delivery</h3>
        <form method="POST" action="{{ url_for('reassign_delivery', delivery_id=delivery.id) }}">
            <select name="agent_id">
                {% for agent in agents %}
                <option value="{{ agent.id }}">{{ agent.name }}</option>
                {% endfor %}
            </select>
            <input type="hidden" name="delivery_id" value="{{ delivery.id }}">
            <button type="submit" class="btn btn-gold">Reassign</button>
        </form>
    </div>
</div>
{% endblock %}''',
        'superadmin_dashboard.html': '''{% extends "base.html" %}
{% block content %}
<h2>SuperAdmin Dashboard</h2>
<div class="row">
    <div class="col-md-4"><div class="card p-3"><h4>Total Users</h4><p>{{ users|length }}</p></div></div>
    <div class="col-md-4"><div class="card p-3"><h4>Products</h4><p>{{ products|length }}</p></div></div>
    <div class="col-md-4"><div class="card p-3"><h4>Orders</h4><p>{{ orders|length }}</p></div></div>
</div>
<h3>Create User</h3>
<form method="POST" action="{{ url_for('superadmin_create_user') }}" class="row g-2 mb-4">
    <div class="col-md-3"><input type="text" name="name" class="form-control" placeholder="Name" required></div>
    <div class="col-md-3"><input type="email" name="email" class="form-control" placeholder="Email" required></div>
    <div class="col-md-2"><input type="text" name="phone" class="form-control" placeholder="Phone"></div>
    <div class="col-md-2"><select name="role" class="form-select"><option>vendor</option><option>technician</option><option>agent</option><option>installer</option><option>manager</option><option>buyer</option></select></div>
    <div class="col-md-2"><input type="password" name="password" class="form-control" placeholder="Password" required></div>
    <div class="col-md-12"><button type="submit" class="btn btn-gold">Create User</button></div>
</form>
<h3>Platform Settings</h3>
<form method="POST" action="{{ url_for('superadmin_settings') }}" class="row g-2">
    <div class="col-md-4"><label>Vendor Commission (%)</label><input type="number" name="vendor_commission" class="form-control" value="{{ settings.vendor_commission * 100 }}" step="0.5" required></div>
    <div class="col-md-4"><label>Agent Base Salary (UGX)</label><input type="number" name="agent_base_salary" class="form-control" value="{{ settings.agent_base_salary }}" required></div>
    <div class="col-md-4"><button type="submit" class="btn btn-gold mt-4">Save Settings</button></div>
</form>
<h3 class="mt-4">Backup / Restore</h3>
<a href="{{ url_for('superadmin_backup') }}" class="btn btn-outline-gold">Download Backup</a>
<form method="POST" action="{{ url_for('superadmin_restore') }}" enctype="multipart/form-data" class="d-inline">
    <input type="file" name="backup_file" accept=".json" required>
    <button type="submit" class="btn btn-outline-gold">Restore</button>
</form>
<h3 class="mt-4">User List</h3>
<table class="table table-dark">
    <thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th>Actions</th></tr></thead>
    <tbody>
    {% for u in users %}
    <tr>
        <td>{{ u.id }}</td><td>{{ u.name }}</td><td>{{ u.email }}</td><td>{{ u.role }}</td>
        <td><a href="{{ url_for('superadmin_delete_user', user_id=u.id) }}" class="btn btn-sm btn-danger" onclick="return confirm('Delete user?')">Delete</a></td>
    </tr>
    {% endfor %}
    </tbody>
</table>
{% endblock %}'''
    }
    for filename, content in templates.items():
        path = os.path.join('templates', filename)
        if not os.path.exists(path):
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

ensure_templates()

# ----------------------------- RUN THE APP -----------------------------
if __name__ == '__main__':
    import os
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(role='superadmin').first():
            admin = User(name='Maxwell', email='maxwell@cybervault.ug', phone='0708725402', role='superadmin')
            admin.set_password('amitra734')
            db.session.add(admin)
            db.session.commit()
        if not Product.query.first():
            demo = Product(name='Samsung Galaxy A54', price=1250000, market_price=1650000, category='Smartphones', stock=25,
                           image_filename=None, description='6.4" display')
            db.session.add(demo)
            db.session.commit()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)