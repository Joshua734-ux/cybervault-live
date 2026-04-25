import os
import json
import io
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# ------------------------------------------------------------
# Flask app setup
# ------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
if os.environ.get('RENDER'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/cybervault.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cybervault.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'customer_login'

# ------------------------------------------------------------
# Database Models (all features)
# ------------------------------------------------------------
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
    image_url = db.Column(db.String(200))
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
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.Column(db.Text)
    delivery_address = db.Column(db.String(200))
    return_reason = db.Column(db.Text)

class Repair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    device = db.Column(db.String(100))
    issue = db.Column(db.Text)
    assigned_technician_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='pending')
    quote = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Delivery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(20))
    agent_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='assigned')
    proof_photo = db.Column(db.String(200))
    completed_at = db.Column(db.DateTime)

class Installation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(20))
    installer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='pending')
    scheduled_date = db.Column(db.DateTime)

class Referral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    referred_email = db.Column(db.String(100))
    reward_claimed = db.Column(db.Boolean, default=False)

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

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------
def get_settings():
    s = PlatformSettings.query.first()
    if not s:
        s = PlatformSettings()
        db.session.add(s)
        db.session.commit()
    return s

def add_audit(action, details):
    if current_user.is_authenticated:
        log = AuditLog(user_id=current_user.id, action=action, details=details)
        db.session.add(log)
        db.session.commit()

def calculate_agent_points(agent_id):
    completed = Delivery.query.filter_by(agent_id=agent_id, status='delivered').count()
    return min(completed, 10)

def calculate_agent_salary(agent_id):
    points = calculate_agent_points(agent_id)
    settings = get_settings()
    return int((points / 10) * settings.agent_base_salary)

# ------------------------------------------------------------
# Ensure templates directory and files exist
# ------------------------------------------------------------
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
<h2 class="mb-4">🔥 Factory Direct Prices</h2>
<div class="row">
    {% for product in products %}
    <div class="col-md-4 col-lg-3 mb-4">
        <div class="card h-100 p-3">
            <img src="{{ product.image_url or 'https://via.placeholder.com/300' }}" class="card-img-top" style="height: 180px; object-fit: cover;">
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
            <img src="{{ product.image_url or 'https://via.placeholder.com/200' }}" class="card-img-top" style="height: 120px; object-fit: cover;">
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
    <a href="{{ url_for('track_order', order_id=order.id) }}" class="btn btn-sm btn-outline-gold">Track</a>
    {% if order.status == 'pending' %}
        <a href="{{ url_for('cancel_order', order_id=order.id) }}" class="btn btn-sm btn-danger">Cancel</a>
    {% endif %}
    {% if order.status == 'delivered' %}
        <form method="POST" action="{{ url_for('return_order', order_id=order.id) }}" class="d-inline">
            <input type="text" name="reason" placeholder="Reason" required>
            <button type="submit" class="btn btn-sm btn-warning">Request Return</button>
        </form>
    {% endif %}
</div>
{% else %}
<p>No orders yet.</p>
{% endfor %}
{% endblock %}''',
        'track_order.html': '''{% extends "base.html" %}
{% block content %}
<h2>Track Order #{{ order.id }}</h2>
<div class="progress mb-3">
    <div class="progress-bar bg-gold" style="width: {% if order.status == 'pending' %}25{% elif order.status == 'processing' %}50{% elif order.status == 'shipped' %}75{% elif order.status == 'delivered' %}100{% else %}0{% endif %}%"></div>
</div>
<p>Status: {{ order.status }}</p>
<p>Estimated delivery: {% if order.status == 'shipped' %}2‑3 days{% else %}Pending{% endif %}</p>
<a href="{{ url_for('customer_orders') }}" class="btn btn-gold">Back</a>
{% endblock %}''',
        'checkout.html': '''{% extends "base.html" %}
{% block content %}
<h2>Checkout</h2>
<form method="POST">
    <div class="mb-3"><label>Delivery Address</label><input type="text" name="address" class="form-control" required></div>
    <div class="card p-3 mb-3">
        <h4>Order Summary</h4>
        {% for item in cart_items %}
            <div>{{ item.product.name }} x{{ item.quantity }} = UGX {{ (item.product.price * item.quantity)|int }}</div>
        {% endfor %}
        <hr>
        <strong>Total: UGX {{ cart_items|sum(attribute='product.price')|int }}</strong>
    </div>
    <button type="submit" class="btn btn-gold">Place Order</button>
</form>
{% endblock %}''',
        'wishlist.html': '''{% extends "base.html" %}
{% block content %}
<h2>My Wishlist</h2>
<div class="row">
    {% for product in products %}
    <div class="col-md-3 mb-3">
        <div class="card p-2">
            <img src="{{ product.image_url or 'https://via.placeholder.com/200' }}" class="card-img-top">
            <h6>{{ product.name }}</h6>
            <div>UGX {{ product.price|int }}</div>
            <a href="{{ url_for('add_to_cart', product_id=product.id) }}" class="btn btn-sm btn-gold">Add to Cart</a>
            <a href="{{ url_for('toggle_wishlist', product_id=product.id) }}" class="btn btn-sm btn-danger">Remove</a>
        </div>
    </div>
    {% endfor %}
</div>
{% endblock %}''',
        'repair_request.html': '''{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card p-4">
            <h2>Request Repair</h2>
            <form method="POST">
                <div class="mb-3"><label>Device</label><input type="text" name="device" class="form-control" required></div>
                <div class="mb-3"><label>Issue</label><textarea name="issue" class="form-control" rows="3" required></textarea></div>
                <button type="submit" class="btn btn-gold">Submit</button>
            </form>
        </div>
    </div>
</div>
{% endblock %}''',
        'my_repairs.html': '''{% extends "base.html" %}
{% block content %}
<h2>My Repairs</h2>
<ul>
    {% for r in repairs %}
    <li>{{ r.device }} - {{ r.status }} ({{ r.created_at.strftime('%Y-%m-%d') }})</li>
    {% endfor %}
</ul>
{% endblock %}''',
        'referral.html': '''{% extends "base.html" %}
{% block content %}
<div class="card p-4 text-center">
    <h2>Refer a Friend</h2>
    <p>Share this link and get UGX 5,000 credit when they sign up:</p>
    <input type="text" class="form-control" value="{{ link }}" id="referralLink" readonly>
    <button class="btn btn-gold mt-2" onclick="copyLink()">Copy Link</button>
</div>
<script>
function copyLink() {
    var copyText = document.getElementById("referralLink");
    copyText.select();
    document.execCommand("copy");
    alert("Link copied!");
}
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
                <span>{{ product.name }} - UGX {{ product.price|int }} (Stock: {{ product.stock }})</span>
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
            <form method="POST" action="{{ url_for('vendor_add_product') }}">
                <input type="text" name="name" class="form-control mb-2" placeholder="Name" required>
                <input type="number" name="price" class="form-control mb-2" placeholder="Price" required>
                <input type="number" name="market_price" class="form-control mb-2" placeholder="Market Price" required>
                <input type="text" name="category" class="form-control mb-2" placeholder="Category">
                <input type="number" name="stock" class="form-control mb-2" placeholder="Stock" required>
                <input type="text" name="image_url" class="form-control mb-2" placeholder="Image URL">
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
<p>Welcome, {{ current_user.name }}</p>
{% for inst in installations %}
<div class="card p-2 mb-2">
    Order {{ inst.order_id }} - Status: {{ inst.status }}
    <form method="POST" action="{{ url_for('installer_update', inst_id=inst.id) }}">
        <select name="status">
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
        </select>
        <button type="submit">Update</button>
    </form>
</div>
{% else %}
<p>No installations assigned.</p>
{% endfor %}
{% endblock %}''',
        'manager_dashboard.html': '''{% extends "base.html" %}
{% block content %}
<h2>Manager Dashboard</h2>
<div class="row">
    <div class="col-md-3"><div class="card p-3 text-center"><h3>{{ vendors }}</h3><p>Vendors</p></div></div>
    <div class="col-md-3"><div class="card p-3 text-center"><h3>{{ orders }}</h3><p>Orders</p></div></div>
    <div class="col-md-3"><div class="card p-3 text-center"><h3>UGX {{ revenue|int }}</h3><p>Revenue</p></div></div>
    <div class="col-md-3"><div class="card p-3 text-center"><h3>{{ disputes }}</h3><p>Open Disputes</p></div></div>
</div>
<a href="{{ url_for('manager_disputes') }}" class="btn btn-gold mt-3">Manage Disputes</a>
{% endblock %}''',
        'manager_disputes.html': '''{% extends "base.html" %}
{% block content %}
<h2>Disputes</h2>
{% for d in disputes %}
<div class="card p-3 mb-2">
    <div>Order {{ d.order_id }} – Reason: {{ d.reason }}</div>
    <form method="POST" action="{{ url_for('resolve_dispute', dispute_id=d.id) }}">
        <input type="text" name="resolution" placeholder="Resolution" class="form-control mb-2">
        <button type="submit" class="btn btn-sm btn-gold">Resolve</button>
    </form>
</div>
{% else %}
<p>No disputes.</p>
{% endfor %}
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

# Call the function to ensure templates are created
ensure_templates()

# ------------------------------------------------------------
# Routes (all business logic)
# ------------------------------------------------------------
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
            add_audit('Customer login', user.email)
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
    recent_ids = session.get('recently_viewed', [])
    recent_products = [Product.query.get(pid) for pid in recent_ids[-4:] if Product.query.get(pid)]
    return render_template('customer_dashboard.html', products=products, cart_items=cart_items, recent_products=recent_products)

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
        flash('Cart is empty', 'danger')
        return redirect(url_for('customer_dashboard'))
    if request.method == 'POST':
        address = request.form['address']
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
        order = Order(id=order_id, user_id=current_user.id, total=total, items=json.dumps(items_list), delivery_address=address)
        db.session.add(order)
        db.session.commit()
        add_audit('Order placed', f'Order {order_id} total UGX {total}')
        flash(f'Order placed! Order ID: {order_id}', 'success')
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

@app.route('/track-order/<order_id>')
@login_required
def track_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and current_user.role != 'superadmin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    return render_template('track_order.html', order=order)

@app.route('/cancel-order/<order_id>')
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id or order.status != 'pending':
        flash('Cannot cancel this order', 'danger')
        return redirect(url_for('customer_orders'))
    order.status = 'cancelled'
    db.session.commit()
    add_audit('Order cancelled', order_id)
    flash('Order cancelled', 'success')
    return redirect(url_for('customer_orders'))

@app.route('/return-order/<order_id>', methods=['POST'])
@login_required
def return_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id or order.status != 'delivered':
        flash('Only delivered orders can be returned', 'danger')
        return redirect(url_for('customer_orders'))
    reason = request.form['reason']
    order.status = 'return-requested'
    order.return_reason = reason
    db.session.commit()
    flash('Return request submitted', 'success')
    return redirect(url_for('customer_orders'))

@app.route('/wishlist/toggle/<int:product_id>')
@login_required
def toggle_wishlist(product_id):
    if current_user.role != 'buyer':
        flash('Please login as customer', 'danger')
        return redirect(url_for('index'))
    existing = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if existing:
        db.session.delete(existing)
        flash('Removed from wishlist', 'info')
    else:
        wish = Wishlist(user_id=current_user.id, product_id=product_id)
        db.session.add(wish)
        flash('Added to wishlist', 'success')
    db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/wishlist')
@login_required
def wishlist_page():
    if current_user.role != 'buyer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    items = Wishlist.query.filter_by(user_id=current_user.id).all()
    products = [item.product for item in items]
    return render_template('wishlist.html', products=products)

@app.route('/repair-request', methods=['GET', 'POST'])
@login_required
def repair_request():
    if current_user.role != 'buyer':
        flash('Only customers can request repairs', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        device = request.form['device']
        issue = request.form['issue']
        repair = Repair(user_id=current_user.id, device=device, issue=issue)
        db.session.add(repair)
        db.session.commit()
        flash('Repair request submitted', 'success')
        return redirect(url_for('customer_dashboard'))
    return render_template('repair_request.html')

@app.route('/my-repairs')
@login_required
def my_repairs():
    if current_user.role != 'buyer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    repairs = Repair.query.filter_by(user_id=current_user.id).all()
    return render_template('my_repairs.html', repairs=repairs)

@app.route('/referral-link')
@login_required
def referral_link():
    if current_user.role != 'buyer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    link = url_for('register', _external=True) + f'?ref={current_user.id}'
    return render_template('referral.html', link=link)

@app.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def add_review(product_id):
    if current_user.role != 'buyer':
        flash('Only customers can review', 'danger')
        return redirect(url_for('index'))
    rating = int(request.form['rating'])
    comment = request.form['comment']
    review = Review(product_id=product_id, user_id=current_user.id, rating=rating, comment=comment)
    db.session.add(review)
    product = Product.query.get(product_id)
    ratings = json.loads(product.ratings)
    ratings.append(rating)
    product.ratings = json.dumps(ratings)
    db.session.commit()
    flash('Review added', 'success')
    return redirect(request.referrer)

@app.route('/recently-viewed/<int:product_id>')
def recently_viewed(product_id):
    recent = session.get('recently_viewed', [])
    if product_id in recent:
        recent.remove(product_id)
    recent.insert(0, product_id)
    session['recently_viewed'] = recent[:5]
    return '', 204

# ------------------------------------------------------------
# Management Login
# ------------------------------------------------------------
@app.route('/management/login', methods=['GET', 'POST'])
def management_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.role != 'buyer' and user.status == 'active':
            login_user(user)
            add_audit('Management login', f'{user.role} {user.email}')
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

# ------------------------------------------------------------
# Vendor Dashboard
# ------------------------------------------------------------
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
    image_url = request.form['image_url']
    desc = request.form['description']
    product = Product(name=name, price=price, market_price=market_price, category=category,
                     stock=stock, image_url=image_url, description=desc, vendor_id=current_user.id)
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

# ------------------------------------------------------------
# Technician Dashboard
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# Agent Dashboard
# ------------------------------------------------------------
@app.route('/agent/dashboard')
@login_required
def agent_dashboard():
    if current_user.role != 'agent':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    deliveries = Delivery.query.filter_by(agent_id=current_user.id).all()
    points = calculate_agent_points(current_user.id)
    salary = calculate_agent_salary(current_user.id)
    return render_template('agent_dashboard.html', deliveries=deliveries, points=points, salary=salary)

@app.route('/agent/update-delivery/<int:delivery_id>', methods=['POST'])
@login_required
def agent_update_delivery(delivery_id):
    if current_user.role != 'agent':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    delivery = db.session.get(Delivery, delivery_id)
    if delivery and delivery.agent_id == current_user.id:
        delivery.status = request.form['status']
        if delivery.status == 'delivered':
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

# ------------------------------------------------------------
# Installer Dashboard
# ------------------------------------------------------------
@app.route('/installer/dashboard')
@login_required
def installer_dashboard():
    if current_user.role != 'installer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    installations = Installation.query.filter_by(installer_id=current_user.id).all()
    return render_template('installer_dashboard.html', installations=installations)

@app.route('/installer/update-installation/<int:inst_id>', methods=['POST'])
@login_required
def installer_update(inst_id):
    if current_user.role != 'installer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    inst = db.session.get(Installation, inst_id)
    if inst and inst.installer_id == current_user.id:
        inst.status = request.form['status']
        db.session.commit()
        flash('Installation updated', 'success')
    return redirect(url_for('installer_dashboard'))

# ------------------------------------------------------------
# Manager Dashboard
# ------------------------------------------------------------
@app.route('/manager/dashboard')
@login_required
def manager_dashboard():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    vendors = User.query.filter_by(role='vendor').count()
    total_orders = Order.query.count()
    total_revenue = db.session.query(db.func.sum(Order.total)).scalar() or 0
    disputes = Dispute.query.filter_by(status='open').count()
    return render_template('manager_dashboard.html', vendors=vendors, orders=total_orders,
                           revenue=total_revenue, disputes=disputes)

@app.route('/manager/disputes')
@login_required
def manager_disputes():
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    disputes = Dispute.query.all()
    return render_template('manager_disputes.html', disputes=disputes)

@app.route('/manager/resolve-dispute/<int:dispute_id>', methods=['POST'])
@login_required
def resolve_dispute(dispute_id):
    if current_user.role != 'manager':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    dispute = db.session.get(Dispute, dispute_id)
    if dispute:
        dispute.status = 'resolved'
        dispute.resolution = request.form['resolution']
        db.session.commit()
        flash('Dispute resolved', 'success')
    return redirect(url_for('manager_disputes'))

# ------------------------------------------------------------
# SuperAdmin Dashboard
# ------------------------------------------------------------
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
    add_audit('Create user', f'Created {role} {email}')
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
    # For security, we do not automatically restore; show message
    flash('Restore feature requires manual merge for security', 'warning')
    return redirect(url_for('superadmin_dashboard'))

# ------------------------------------------------------------
# Logout
# ------------------------------------------------------------
@app.route('/logout')
@login_required
def logout():
    add_audit('Logout', current_user.email)
    logout_user()
    return redirect(url_for('index'))

# ------------------------------------------------------------
# Run the app
# ------------------------------------------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create default superadmin if none exists
        if not User.query.filter_by(role='superadmin').first():
            admin = User(name='Maxwell', email='maxwell@cybervault.ug', phone='0708725402', role='superadmin')
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)