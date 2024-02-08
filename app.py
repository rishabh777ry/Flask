from datetime import timedelta
from sqlalchemy import func
from running import *
import soldtableclean
import xlsxwriter

app.app_context().push()



class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)


class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(100))
    product_price = db.Column(db.Float)
    quantity = db.Column(db.Integer)
    total_price = db.Column(db.Float)
    date = db.Column(db.Date)

    def __init__(self, product_name, product_price, quantity, total_price, date):
        self.product_name = product_name
        self.product_price = product_price
        self.quantity = quantity
        self.total_price = total_price
        self.date = date


class SoldItem(db.Model):
    __tablename__ = 'Sales'
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(100))
    quantity = db.Column(db.String(100))
    total_price = db.Column(db.Float)
    method = db.Column(db.String(100))
    date = db.Column(db.Date)

    def __init__(self, product_name, quantity, total_price, date, method):
        self.product_name = product_name
        self.quantity = quantity
        self.total_price = total_price
        self.date = date
        self.method = method


class Menu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_category = db.Column(db.String(100))
    product_name = db.Column(db.String(100), unique=True)
    product_rate = db.Column(db.Integer)

    def __init__(self, product_category, product_name, product_rate):
        self.product_category = product_category
        self.product_name = product_name
        self.product_rate = product_rate


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route('/', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            login_user(user)
            return redirect(url_for('index'))
        else:
            return 'Invalid credentials'

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return 'Logged out successfully'


@app.route('/main')
@login_required
def index():
    return render_template('index.html')


@app.route('/add_stock', methods=['GET', 'POST'])
@login_required
def add_stock():
    form = InventoryItemForm()
    inventory = InventoryItem.query.all()

    if form.validate_on_submit():
        product_name = form.product_name.data
        product_price = form.product_price.data
        quantity = form.quantity.data
        date = form.date.data
        total_price = product_price * quantity

        product_found = False

        for record in inventory:
            if record.product_name == product_name and record.date == date:
                record.product_price += product_price
                record.total_price += total_price
                record.date = date
                record.quantity += quantity
                db.session.commit()
                product_found = True
                break

        if not product_found:
            new_item = InventoryItem(
                product_name=product_name,
                product_price=product_price,
                quantity=quantity,
                total_price=total_price,
                date=date
            )
            db.session.add(new_item)
            db.session.commit()
            flash('Stock added successfully!', 'success')  # Flash message added

        return redirect(url_for('add_stock'))
    return render_template('addstock.html', form=form, inventory=inventory)


@app.route('/place_order', methods=['POST', 'GET'])
@login_required
def billing():
    inventory = Menu.query.all()

    if request.method == 'POST' or request.method == 'GET':
        category = request.form.get('category')
        products_selected = request.form.get('selectedProducts')
        rst = soldtableclean.Soldtableclean(products_selected).str_to_list()
        item = soldtableclean.Setdatabase(rst).list_of_item()
        quantity = soldtableclean.Setdatabase(rst).list_of_quantities()

        date = datetime.datetime.now()
        method = request.form.get('paymentMethod')

        quantity_str = ','.join(str(q) for q in quantity) if all(quantity) else '0'

        total_price = 0
        for i in item:
            menu_item = Menu.query.filter_by(product_name=i).first()
            if menu_item:
                total_price += menu_item.product_rate
        print('category',category)
        if category is None:
            flash('Add items to proceed')
        else:
            billing_item = SoldItem(
                product_name=','.join(item),
                quantity=quantity_str,
                total_price=total_price,
                date=date,
                method=method
            )
            db.session.add(billing_item)
            db.session.commit()
            flash('Order placed successfully!', 'success')  # Flash message added
            return redirect(url_for('order_confirmation'))  # Redirect to the order confirmation page

        return render_template('billing.html', inventory=inventory,
                               categories=set(item.product_category for item in inventory))
    else:
        return redirect('index')

@app.route('/order_confirmation')
def order_confirmation():
    return render_template('order_confirmation.html')
@app.route('/get_categories')
def get_categories():
    menu = Menu.query.all()
    categories = set(list(item.product_category for item in menu))
    return jsonify(categories)


@app.route('/get_products/<category>')
def get_products(category):
    menu = Menu.query.all()
    products = [item.product_name for item in menu if item.product_category == category]
    return jsonify(products)


@app.route('/admin')
@login_required
def admin():
    today = datetime.date.today()
    previous_two_days = [today - timedelta(days=i) for i in range(2, -1, -1)]
    formatted_dates = [date.strftime('%Y-%m-%d') for date in previous_two_days]
    chart_data = {
        'today_revenue': SoldItem.query.filter_by(date=today).with_entities(
            func.sum(SoldItem.total_price)).scalar() or 0,

        'labels': formatted_dates,
        'data': [
            SoldItem.query.filter_by(date=date).with_entities(func.sum(SoldItem.total_price)).scalar() or 0
            for date in formatted_dates
        ],
    }
    online_data = SoldItem.query.filter_by(date=today, method='online').with_entities(
        func.sum(SoldItem.total_price)).scalar() or 0

    cash_data = SoldItem.query.filter_by(date=today, method='offline').with_entities(
        func.sum(SoldItem.total_price)).scalar() or 0

    pie_data = {
        'labels': ['Online', 'Cash'],
        'data': [online_data, cash_data],
    }
    return render_template('admin.html', chart_data=chart_data, pie_data=pie_data)


@app.route('/delete_item/<int:id>', methods=['POST'])
@login_required
def delete_item(id):
    item_to_delete = Menu.query.get_or_404(id)
    db.session.delete(item_to_delete)
    db.session.commit()
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('update_menu'))


@app.route('/update_menu', methods=['POST', 'GET'])
@login_required
def update_menu():
    form = UpdateMenu()
    menu = Menu.query.all()
    if form.validate_on_submit():
        name = str.lower(form.Item.data)
        price = form.Price.data
        category = str.upper(form.Category.data)
        name = name.replace(' ', '-')
        updateproduct = Menu.query.filter_by(product_category=category, product_name=name).first()
        if updateproduct:
            updateproduct.product_rate = price
        else:
            new_item = Menu(product_category=str.upper(category), product_name=str.lower(name), product_rate=price)
            db.session.add(new_item)
        db.session.commit()
        flash('Menu updated successfully!', 'success')  # Flash message added

    return render_template('updatemenu.html', menu=menu, form=form)


@app.route('/view_inventory')
@login_required
def view_inventory():
    inventory = InventoryItem.query.all()
    return render_template('view_inventory.html', inventory=inventory)


@app.route('/download_menu_excel', methods=['GET'])
@login_required
def download_menu_excel():
    start_date_param = request.args.get('start_date')
    end_date_param = request.args.get('end_date')

    if not (start_date_param and end_date_param):
        return "Both start_date and end_date parameters are required.", 400

    sales = SoldItem.query.filter(SoldItem.date.between(start_date_param, end_date_param)).all()

    excel_file_path = f'sales' + str(datetime.date.today()) + '.xlsx'
    workbook = xlsxwriter.Workbook(excel_file_path)
    worksheet = workbook.add_worksheet()

    headers = ['ID', 'Product Name', 'Total Price', 'Quantity', 'Payment Mode']
    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header)

    for row_num, item in enumerate(sales, start=1):
        worksheet.write(row_num, 0, item.id)
        worksheet.write(row_num, 1, item.product_name)
        worksheet.write(row_num, 2, item.quantity)
        worksheet.write(row_num, 3, item.total_price)
        worksheet.write(row_num, 4, item.method)

    workbook.close()

    return send_file(excel_file_path, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)  
