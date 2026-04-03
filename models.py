import json
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    unit = db.Column(db.String(20), default='شريط')
    price_per_unit = db.Column(db.Float, nullable=False, default=0.0)
    current_stock = db.Column(db.Float, default=0.0)

class DailyVoucher(db.Model):
    __tablename__ = 'daily_vouchers'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.today)
    ticket_number = db.Column(db.String(50), nullable=False)
    items_data = db.Column(db.Text, nullable=False)  # JSON: [{item_id, quantity}]
    reviewed = db.Column(db.Boolean, default=False)
    reviewed_by = db.Column(db.String(100))
    reviewed_modifications = db.Column(db.Text, nullable=True)  # JSON للتعديلات
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Ledger223(db.Model):
    __tablename__ = 'ledger223'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    summary_data = db.Column(db.Text)  # JSON summary per item

class Order111(db.Model):
    __tablename__ = 'order111'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    date = db.Column(db.Date, nullable=False)
    items_data = db.Column(db.Text, nullable=False)  # JSON: [{item_id, quantity, requested_price?}]
    status = db.Column(db.String(20), default='pending')
    total_value = db.Column(db.Float, default=0.0)

class Order112(db.Model):
    __tablename__ = 'order112'
    id = db.Column(db.Integer, primary_key=True)
    order111_id = db.Column(db.Integer, db.ForeignKey('order111.id'), nullable=False)
    received_date = db.Column(db.Date, nullable=False)
    items_data = db.Column(db.Text, nullable=False)  # JSON: [{item_id, quantity_received, expiry_date, batch_no, price}]
    total_value = db.Column(db.Float, default=0.0)
    order111 = db.relationship('Order111', backref=db.backref('receivings', lazy=True))

    # إضافة حقل مساعد لاستخراج الكمية المستلمة لكل صنف بسهولة
    @property
    def quantity_received(self):
        # تستخدم في المجاميع
        total = 0.0
        items = json.loads(self.items_data)
        for it in items:
            total += it.get('quantity_received', 0)
        return total

class Ledger5(db.Model):
    __tablename__ = 'ledger5'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    entry_type = db.Column(db.String(10))  # 'in' or 'out'
    reference_number = db.Column(db.String(50))
    value = db.Column(db.Float)

class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    theoretical_stock = db.Column(db.Float)
    actual_stock = db.Column(db.Float)
    difference = db.Column(db.Float)
    inventory_date = db.Column(db.Date, default=datetime.today)
    item = db.relationship('Item', backref='inventories')

class SystemConfig(db.Model):
    __tablename__ = 'system_config'
    id = db.Column(db.Integer, primary_key=True)
    month_start_day = db.Column(db.Integer, default=26)
    fiscal_year_start_month = db.Column(db.Integer, default=1)