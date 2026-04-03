from flask import Flask, render_template, request, jsonify
from models import db, Item, DailyVoucher, Ledger223, Ledger118, Order111, Order112, Ledger5, Inventory, SystemConfig
from datetime import datetime, date, timedelta
from sqlalchemy import func
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'

# ------------------- إعداد قاعدة البيانات -------------------
if os.environ.get('VERCEL_ENV') or os.environ.get('DATABASE_URL'):
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///pharmacy.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pharmacy.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# إنشاء الجداول إذا لم تكن موجودة (مرة واحدة عند بدء التشغيل)
with app.app_context():
    db.create_all()
    # إعدادات افتراضية للنظام إذا لم توجد
    if SystemConfig.query.count() == 0:
        config = SystemConfig(month_start_day=26, fiscal_year_start_month=1)
        db.session.add(config)
        db.session.commit()

# ------------------- دوال مساعدة -------------------
def get_fiscal_month(target_date):
    """إرجاع السنة والشهر الحكومي بناءً على يوم 26"""
    if target_date.day >= 26:
        month = target_date.month + 1 if target_date.month < 12 else 1
        year = target_date.year if target_date.month < 12 else target_date.year + 1
    else:
        month = target_date.month
        year = target_date.year
    return year, month

def get_fiscal_month_range(year, month):
    """إرجاع (تاريخ البدء، تاريخ الانتهاء) لشهر حكومي معين"""
    if month == 1:
        start_date = date(year-1, 12, 26)
    else:
        start_date = date(year, month-1, 26)
    end_date = date(year, month, 25)
    return start_date, end_date

# ------------------- Routes -------------------
@app.route('/')
def index():
    return render_template('index.html')

# ------------------- إدارة الأصناف -------------------
@app.route('/api/items', methods=['GET', 'POST'])
def manage_items():
    if request.method == 'GET':
        items = Item.query.order_by(Item.code).all()
        return jsonify([{
            'id': i.id,
            'code': i.code,
            'name': i.name,
            'unit': i.unit,
            'price_per_unit': float(i.price_per_unit),
            'current_stock': i.current_stock
        } for i in items])
    else:
        data = request.json
        if not data.get('code') or not data.get('name'):
            return jsonify({'error': 'الكود والاسم مطلوبان'}), 400
        item = Item(
            code=data['code'],
            name=data['name'],
            unit=data.get('unit', 'شريط'),
            price_per_unit=data.get('price_per_unit', 0.0),
            current_stock=data.get('current_stock', 0.0)
        )
        db.session.add(item)
        db.session.commit()
        return jsonify({'message': 'تمت إضافة الصنف', 'id': item.id})

@app.route('/api/items/<int:id>', methods=['PUT', 'DELETE'])
def update_delete_item(id):
    item = Item.query.get_or_404(id)
    if request.method == 'PUT':
        data = request.json
        item.name = data.get('name', item.name)
        item.code = data.get('code', item.code)
        item.unit = data.get('unit', item.unit)
        item.price_per_unit = data.get('price_per_unit', item.price_per_unit)
        item.current_stock = data.get('current_stock', item.current_stock)
        db.session.commit()
        return jsonify({'message': 'تم التحديث'})
    else:
        db.session.delete(item)
        db.session.commit()
        return jsonify({'message': 'تم الحذف'})

# ------------------- اليومية (ت ص 9) -------------------
@app.route('/daily_voucher')
def daily_voucher_page():
    return render_template('daily_voucher.html')

@app.route('/api/daily_voucher', methods=['GET', 'POST'])
def daily_voucher_api():
    if request.method == 'POST':
        data = request.json
        try:
            voucher_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except:
            voucher_date = date.today()
        voucher = DailyVoucher(
            date=voucher_date,
            ticket_number=data['ticket_number'],
            items_data=json.dumps(data['items']),
            reviewed=False
        )
        db.session.add(voucher)
        # تحديث المخزون (منصرف)
        for itm in data['items']:
            item = Item.query.get(itm['item_id'])
            if item:
                item.current_stock -= itm['quantity']
        db.session.commit()
        return jsonify({'message': 'تم تسجيل التذكرة', 'id': voucher.id})
    else:
        vouchers = DailyVoucher.query.order_by(DailyVoucher.date.desc(), DailyVoucher.ticket_number.desc()).all()
        return jsonify([{
            'id': v.id,
            'date': v.date.isoformat(),
            'ticket_number': v.ticket_number,
            'items': json.loads(v.items_data),
            'reviewed': v.reviewed
        } for v in vouchers])

@app.route('/api/daily_voucher/<int:id>/review', methods=['PUT'])
def review_voucher(id):
    voucher = DailyVoucher.query.get_or_404(id)
    data = request.json or {}
    voucher.reviewed = True
    voucher.reviewed_by = data.get('reviewed_by', 'الشطب')
    if 'modified_items' in data:
        original_items = json.loads(voucher.items_data)
        modified = data['modified_items']
        for mod in modified:
            for idx, orig in enumerate(original_items):
                if orig['item_id'] == mod['item_id']:
                    diff = mod['new_quantity'] - orig['quantity']
                    if diff != 0:
                        item = Item.query.get(mod['item_id'])
                        if item:
                            item.current_stock -= diff
                    original_items[idx]['quantity'] = mod['new_quantity']
        voucher.items_data = json.dumps(original_items)
        voucher.reviewed_modifications = json.dumps(modified)
    db.session.commit()
    return jsonify({'message': 'تمت المراجعة'})

# ------------------- دفتر 223 -------------------
@app.route('/ledger223')
def ledger223_page():
    return render_template('ledger223.html')

@app.route('/api/ledger223', methods=['GET'])
def get_ledger223():
    daily_summary = {}
    vouchers = DailyVoucher.query.order_by(DailyVoucher.date).all()
    for v in vouchers:
        d = v.date.isoformat()
        if d not in daily_summary:
            daily_summary[d] = {}
        items = json.loads(v.items_data)
        for it in items:
            item = Item.query.get(it['item_id'])
            name = item.name if item else f"صنف {it['item_id']}"
            daily_summary[d][name] = daily_summary[d].get(name, 0) + it['quantity']
    result = [{'date': d, 'items_summary': s} for d, s in daily_summary.items()]
    return jsonify(result)

# ------------------- دفتر 118 -------------------
@app.route('/ledger118')
def ledger118_page():
    return render_template('ledger118.html')

@app.route('/api/ledger118', methods=['GET'])
def get_ledger118():
    items = Item.query.all()
    result = []
    for item in items:
        incoming_qty = db.session.query(func.sum(Order112.quantity_received)).filter(Order112.item_id == item.id).scalar() or 0.0
        outgoing_qty = 0.0
        vouchers = DailyVoucher.query.all()
        for v in vouchers:
            items_data = json.loads(v.items_data)
            for it in items_data:
                if it['item_id'] == item.id:
                    outgoing_qty += it['quantity']
        balance = incoming_qty - outgoing_qty
        result.append({
            'item_id': item.id,
            'item_name': item.name,
            'incoming': incoming_qty,
            'outgoing': outgoing_qty,
            'theoretical_balance': balance,
            'actual_balance': item.current_stock,
            'price_per_unit': float(item.price_per_unit),
            'total_value': balance * item.price_per_unit
        })
    return jsonify(result)

# ------------------- إذن 111 -------------------
@app.route('/order111')
def order111_page():
    return render_template('order111.html')

@app.route('/api/order111', methods=['GET', 'POST'])
def order111_api():
    if request.method == 'POST':
        data = request.json
        order = Order111(
            order_number=data['order_number'],
            date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
            items_data=json.dumps(data['items']),
            status='pending',
            total_value=data.get('total_value', 0.0)
        )
        db.session.add(order)
        db.session.commit()
        return jsonify({'message': 'تم إنشاء إذن الطلب', 'id': order.id})
    else:
        orders = Order111.query.order_by(Order111.order_number.desc()).all()
        return jsonify([{
            'id': o.id,
            'order_number': o.order_number,
            'date': o.date.isoformat(),
            'items': json.loads(o.items_data),
            'status': o.status,
            'total_value': float(o.total_value)
        } for o in orders])

@app.route('/api/order111/<int:id>', methods=['PUT'])
def update_order111(id):
    order = Order111.query.get_or_404(id)
    data = request.json
    if 'status' in data:
        order.status = data['status']
    if 'items' in data:
        order.items_data = json.dumps(data['items'])
    db.session.commit()
    return jsonify({'message': 'تم التحديث'})

# ------------------- دفتر 112 -------------------
@app.route('/order112')
def order112_page():
    return render_template('order112.html')

@app.route('/api/order112', methods=['GET', 'POST'])
def order112_api():
    if request.method == 'POST':
        data = request.json
        received = Order112(
            order111_id=data['order111_id'],
            received_date=datetime.strptime(data['received_date'], '%Y-%m-%d').date(),
            items_data=json.dumps(data['items']),
            total_value=data.get('total_value', 0.0)
        )
        db.session.add(received)
        for it in data['items']:
            item = Item.query.get(it['item_id'])
            if item:
                item.current_stock += it['quantity_received']
        db.session.commit()
        order111 = Order111.query.get(data['order111_id'])
        if order111:
            order111.status = 'received'
            db.session.commit()
        return jsonify({'message': 'تم تسجيل الوارد'})
    else:
        received_list = Order112.query.order_by(Order112.received_date.desc()).all()
        return jsonify([{
            'id': r.id,
            'order111_id': r.order111_id,
            'received_date': r.received_date.isoformat(),
            'items': json.loads(r.items_data),
            'total_value': float(r.total_value)
        } for r in received_list])

# ------------------- دفتر 5 -------------------
@app.route('/ledger5')
def ledger5_page():
    return render_template('ledger5.html')

@app.route('/api/ledger5', methods=['GET'])
def get_ledger5():
    incoming_value = db.session.query(func.sum(Order112.total_value)).scalar() or 0.0
    outgoing_value = 0.0
    vouchers = DailyVoucher.query.all()
    for v in vouchers:
        items = json.loads(v.items_data)
        for it in items:
            item = Item.query.get(it['item_id'])
            if item:
                outgoing_value += it['quantity'] * item.price_per_unit
    balance = incoming_value - outgoing_value
    return jsonify({
        'total_incoming_value': incoming_value,
        'total_outgoing_value': outgoing_value,
        'balance': balance
    })

@app.route('/api/ledger5/transactions', methods=['GET'])
def ledger5_transactions():
    incoming_trans = []
    orders112 = Order112.query.all()
    for o in orders112:
        incoming_trans.append({
            'date': o.received_date.isoformat(),
            'type': 'وارد',
            'reference': f'إذن 111 رقم {o.order111_id}',
            'value': float(o.total_value)
        })
    outgoing_trans = []
    vouchers = DailyVoucher.query.all()
    for v in vouchers:
        total = 0.0
        items = json.loads(v.items_data)
        for it in items:
            item = Item.query.get(it['item_id'])
            if item:
                total += it['quantity'] * item.price_per_unit
        outgoing_trans.append({
            'date': v.date.isoformat(),
            'type': 'منصرف',
            'reference': f'تذكرة رقم {v.ticket_number}',
            'value': total
        })
    all_trans = incoming_trans + outgoing_trans
    all_trans.sort(key=lambda x: x['date'])
    return jsonify(all_trans)

# ------------------- الجرد -------------------
@app.route('/inventory')
def inventory_page():
    return render_template('inventory.html')

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    items = Item.query.all()
    inventory_list = []
    for item in items:
        inventory_list.append({
            'id': item.id,
            'code': item.code,
            'name': item.name,
            'unit': item.unit,
            'theoretical_stock': item.current_stock,
            'actual_stock': None,
            'difference': None,
            'price_per_unit': float(item.price_per_unit),
            'total_value': item.current_stock * item.price_per_unit
        })
    return jsonify(inventory_list)

@app.route('/api/inventory/finalize', methods=['POST'])
def finalize_inventory():
    data = request.json
    for d in data:
        item = Item.query.get(d['item_id'])
        if item:
            diff = d['actual_stock'] - item.current_stock
            inv = Inventory(
                item_id=item.id,
                theoretical_stock=item.current_stock,
                actual_stock=d['actual_stock'],
                difference=diff,
                inventory_date=date.today()
            )
            db.session.add(inv)
            item.current_stock = d['actual_stock']
    db.session.commit()
    return jsonify({'message': 'تم تحديث الجرد'})

# ------------------- التقارير -------------------
@app.route('/report')
def report_page():
    return render_template('report.html')

@app.route('/api/report/monthly', methods=['GET'])
def monthly_report():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    if not year or not month:
        return jsonify({'error': 'يجب تحديد السنة والشهر'}), 400
    start_date, end_date = get_fiscal_month_range(year, month)
    vouchers = DailyVoucher.query.filter(DailyVoucher.date.between(start_date, end_date)).all()
    total_outgoing_value = 0.0
    items_sold = {}
    for v in vouchers:
        items = json.loads(v.items_data)
        for it in items:
            item = Item.query.get(it['item_id'])
            if item:
                val = it['quantity'] * item.price_per_unit
                total_outgoing_value += val
                items_sold[item.name] = items_sold.get(item.name, 0) + it['quantity']
    orders_in = Order112.query.filter(Order112.received_date.between(start_date, end_date)).all()
    total_incoming_value = sum(o.total_value for o in orders_in)
    return jsonify({
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'total_incoming_value': total_incoming_value,
        'total_outgoing_value': total_outgoing_value,
        'net_movement': total_incoming_value - total_outgoing_value,
        'items_sold': items_sold
    })

@app.route('/api/report/inventory_movement', methods=['GET'])
def inventory_movement_report():
    item_id = request.args.get('item_id', type=int)
    if not item_id:
        return jsonify({'error': 'يجب تحديد صنف'}), 400
    item = Item.query.get_or_404(item_id)
    incoming_movements = []
    orders112 = Order112.query.filter(Order112.items_data.contains(f'"item_id": {item_id}')).all()
    for o in orders112:
        items = json.loads(o.items_data)
        for it in items:
            if it['item_id'] == item_id:
                incoming_movements.append({
                    'date': o.received_date.isoformat(),
                    'type': 'وارد',
                    'quantity': it['quantity_received'],
                    'reference': f'إذن 111 رقم {o.order111_id}'
                })
    outgoing_movements = []
    vouchers = DailyVoucher.query.all()
    for v in vouchers:
        items = json.loads(v.items_data)
        for it in items:
            if it['item_id'] == item_id:
                outgoing_movements.append({
                    'date': v.date.isoformat(),
                    'type': 'منصرف',
                    'quantity': it['quantity'],
                    'reference': f'تذكرة {v.ticket_number}'
                })
    movements = incoming_movements + outgoing_movements
    movements.sort(key=lambda x: x['date'])
    return jsonify(movements)

# نقطة نهاية مؤقتة لإنشاء الجداول يدوياً (يمكن إزالتها بعد أول استخدام)
@app.route('/create-db')
def create_db():
    db.create_all()
    return "Tables created successfully!"

# ------------------- تشغيل التطبيق -------------------
if __name__ == '__main__':
    app.run(debug=True)
# هذا السطر مهم جداً لـ Vercel
app = app  # أو لا حاجة، المهم أن يكون هناك متغير app على مستوى الوحدة    
