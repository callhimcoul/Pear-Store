import os
import psycopg2
from flask import Flask, render_template, request, redirect, session, url_for, flash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'pear-secret'

DB_URL = os.environ.get('DATABASE_URL', 'postgresql://pear:pear123@localhost:5432/pearstore')

def get_db():
    return psycopg2.connect(DB_URL)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                                                     id SERIAL PRIMARY KEY,
                                                     username TEXT,
                                                     password TEXT
                );
                CREATE TABLE IF NOT EXISTS products (
                                                        id SERIAL PRIMARY KEY,
                                                        name TEXT,
                                                        description TEXT,
                                                        image TEXT
                );
                CREATE TABLE IF NOT EXISTS reviews (
                                                       id SERIAL PRIMARY KEY,
                                                       product_id INTEGER,
                                                       reviewer TEXT,
                                                       review TEXT,
                                                       rating INTEGER
                );
                """)
    cur.execute("SELECT COUNT(*) FROM products;")
    if cur.fetchone()[0] == 0:
        cur.execute("""
                    INSERT INTO products(name, description, image) VALUES
                                                                       ('PearPhone 1', 'Premium pear device #1.', '1.jpeg'),
                                                                       ('PearPhone 2', 'Premium pear device #2.', '2.jpeg'),
                                                                       ('PearPhone 3', 'Premium pear device #3.', '3.jpeg'),
                                                                       ('PearPhone 4', 'Premium pear device #4.', '4.jpeg'),
                                                                       ('PearPhone 5', 'Premium pear device #5.', '5.jpeg'),
                                                                       ('PearPhone 6', 'Premium pear device #6.', '6.jpeg');
                    """)
    cur.execute("SELECT COUNT(*) FROM users;")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO users(username, password) VALUES('admin', 'admin123'),('user', 'user');")
    conn.commit()
    cur.close()
    conn.close()



# damit nur login user cart adden dürfen

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('username'):

            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped






@app.route('/')
def index():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM products;')
    products = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('store.html', products=products)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ""
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        conn = get_db()
        cur = conn.cursor()

        try:
            query = f"SELECT * FROM users WHERE username='{u}' AND password='{p}';"
            cur.execute(query)
            user = cur.fetchone()
            if user:
                session['username'] = u
                cur.close()
                conn.close()
                return redirect(url_for('index'))
            error = "Login failed!"
        except Exception as e:
            error = f"Database Error: {str(e)}"
        cur.close()
        conn.close()
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ""
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute(f"INSERT INTO users(username, password) VALUES('{u}', '{p}');")
            conn.commit()
            msg = "Registered! You can now login."
        except Exception as e:
            msg = f"Registration Error: {str(e)}"
        cur.close()
        conn.close()
        if "Registered" in msg:
            return redirect(url_for('login'))
    return render_template('register.html', msg=msg)

@app.route('/product/<int:prod_id>', methods=['GET', 'POST'])
def product(prod_id):
    review_msg = ""
    conn = get_db()
    cur = conn.cursor()
    if request.method == 'POST':
        comment = request.form['review']
        rating = int(request.form['rating'])
        user = session.get('username', 'anon')

        cur.execute(
            "INSERT INTO reviews(product_id, reviewer, review, rating) VALUES (%s, %s, %s, %s);",
            (prod_id, user, comment, rating)
        )
        conn.commit()
        review_msg = "Review submitted!"
    cur.execute(f"SELECT * FROM products WHERE id={prod_id};")
    product = cur.fetchone()
    cur.execute(f"SELECT reviewer, review, rating FROM reviews WHERE product_id={prod_id};")
    reviews = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('review.html', product=product, reviews=reviews, review_msg=review_msg)



# -- Cart--



def _get_cart():
    cart = session.get('cart')
    if not isinstance(cart, dict):
        cart = {}
        session['cart'] = cart
    return cart

@app.context_processor
def inject_cart_count():
    cart = session.get('cart', {})

    return {'cart_count': sum(cart.values())}




# --Cart endpoints --


@app.route('/cart')
@login_required
def view_cart():
    cart = session.get('cart', {})
    items = []

    if cart:



        id_values = []
        for k in list(cart.keys()):

            if isinstance(k, str) and k.isdigit():
                id_values.append(int(k))
            else:

                id_values.append(str(k))

        session['cart'] = cart  # keep as-is




        if id_values:
            conn = get_db()
            cur = conn.cursor()

            sql = "SELECT id, name, description, image FROM products WHERE id = %s;"
            rows = []

            try:
                for pid in id_values:


                    cur.execute(sql, (pid,))
                    rec = cur.fetchone()
                    if rec:
                        rows.append(rec)
            finally:
                cur.close()
                conn.close()

            items = [
                {
                    'id': r[0],
                    'name': r[1],
                    'description': r[2],
                    'image': r[3],
                    'qty': cart.get(str(r[0]), 0)
                }
                for r in rows
            ]

    total_qty = sum(i['qty'] for i in items)
    return render_template('cart.html', items=items, total_qty=total_qty)



@app.route('/cart/add/<prod_id>', methods=['GET', 'POST'])
@login_required
def add_to_cart(prod_id):


    cart = _get_cart()



    key = prod_id



    qty_raw = request.values.get('qty', '1')
    try:
        qty = int(qty_raw)
    except Exception:


        qty = qty_raw


    current = cart.get(key, 0)
    try:
        cart[key] = current + qty
    except Exception:

        cart[key] = qty


    session['cart'] = cart


    next_url = request.args.get('next')
    return redirect(next_url or request.referrer or url_for('index'))


@app.route('/cart/remove/<prod_id>', methods=['POST'])
def remove_from_cart(prod_id):
    cart = _get_cart()
    cart.pop(str(prod_id), None)
    session['cart'] = cart
    return redirect(url_for('view_cart'))

@app.route('/cart/update/<prod_id>', methods=['POST'])
def update_cart_item(prod_id):
    cart = _get_cart()
    key = str(prod_id)
    try:
        qty = int(request.form.get('qty', '1'))
    except ValueError:
        qty = 1
    qty = max(0, min(qty, 99))
    if qty == 0:
        cart.pop(key, None)
    else:
        cart[key] = qty
    session['cart'] = cart
    return redirect(url_for('view_cart'))



@app.route('/cart/clear', methods=['POST'])
def clear_cart():
    session.pop('cart', None)
    # optional: from flask import flash
    # flash('Cart cleared.')
    return redirect(url_for('view_cart'))





# ---- Checkout ----

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        return redirect(url_for('view_cart'))

    # Fetch products for items in the cart
    ids = []
    for k in list(cart.keys()):
        if isinstance(k, str) and k.isdigit():
            ids.append(int(k))
        else:
            ids.append(str(k))

    conn = get_db()
    cur = conn.cursor()
    placeholders = ",".join(["%s"] * len(ids))
    sql = f"SELECT id, name, description, image FROM products WHERE id IN ({placeholders});"
    cur.execute(sql, ids)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # Build cart items with quantity
    items = []
    for r in rows:
        items.append({
            'id': r[0],
            'name': r[1],
            'description': r[2],
            'image': r[3],
            'qty': cart.get(str(r[0]), 0)
        })

    total_items = sum(i['qty'] for i in items)

    if request.method == 'POST':
        # fake process checkout
        name = request.form.get('name')
        address = request.form.get('address')
        card = request.form.get('card')
        session.pop('cart', None)
        return render_template('checkout_success.html',
                               name=name,
                               address=address,
                               total_items=total_items)

    return render_template('checkout.html', items=items, total_items=total_items)



@app.route('/admin', methods=['GET'])
def admin_panel():


    if session.get('username') != 'admin':

        return "Admins only. Tip: login as 'admin'.", 403


    delete_user = request.args.get('delete')
    msg = ""
    if delete_user:
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute(f"DELETE FROM users WHERE username='{delete_user}';")
            conn.commit()
            cur.close()
            conn.close()
            msg = f"User '{delete_user}' deleted."
        except Exception as e:
            msg = f"Delete error: {e}"


    sort = request.args.get('sort', 'id')
    direction = request.args.get('dir', 'ASC') #

    query = f"SELECT id, username, password FROM users ORDER BY {sort} {direction};"

    users = []
    err = ""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(query)
        users = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        err = f"Query error: {e}"


    return render_template('admin.html',
                           users=users,
                           err=err,
                           msg=request.args.get('msg', msg),
                           query_used=query)


@app.route('/admin/impersonate', methods=['GET'])
def admin_impersonate():

    who = request.args.get('as', 'user')
    session['username'] = who

    if who == 'user':
            return redirect(url_for('index'))

    if who == 'admin':
                return redirect(url_for('index'))


    nxt = request.args.get('next', url_for('admin_panel'))
    return redirect(nxt)












if __name__ == '__main__':
    init_db()
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
