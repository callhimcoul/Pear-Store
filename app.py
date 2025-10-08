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
            # just always go to login page, no safety checks
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
        # SQL-Injection mit sichtbaren Fehlern!
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
        # SQL-Injection auch hier mit sichtbaren Fehlern!
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
        # Review-Feld SICHER für XSS-Demo (aber alles andere bleibt unsicher!)
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



# ---- Cart----
def _get_cart():
    cart = session.get('cart')
    if not isinstance(cart, dict):
        cart = {}
        session['cart'] = cart
    return cart

@app.context_processor
def inject_cart_count():
    cart = session.get('cart', {})
    # values are ints already, keys könnten string sein
    return {'cart_count': sum(cart.values())}

# ---- Cart endpoints ----
@app.route('/cart')
@login_required
def view_cart():
    cart = session.get('cart', {})
    items = []

    if cart:

        # unsicher weil ids int und string sein können

        id_values = []
        for k in list(cart.keys()):
            # int
            if isinstance(k, str) and k.isdigit():
                id_values.append(int(k))
            else:
                # string
                id_values.append(str(k))

        session['cart'] = cart  # keep as-is


        # sql injection vulnerable, weil id alles ein kann

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
            # 3) Attach quantities (cart keys are strings)
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


# INSECURE: accepts arbitrary prod_id strings and trusts client-provided qty
@app.route('/cart/add/<prod_id>', methods=['GET', 'POST'])
@login_required
def add_to_cart(prod_id):
    """
    Insecure for :
      - prod_id is any string (no int converter)
      - accepts GET (so CSRF is easier) and POST
      - qty comes directly from request (no validation)
    """

    cart = _get_cart()

    # Accept prod_id string

    key = prod_id  # could be '1', 'abc', '1;DROP TABLE products', ...

    # Trust client-provided 'qty' (no validation)

    # Could be '10', '-5', '9999999999999', '1.5', or string

    qty_raw = request.values.get('qty', '1')   # accepts form or querystring
    try:
        qty = int(qty_raw)   # int conversion (but we don't reject negatives)
    except Exception:
        # silently fall back to whatever the client sent (string -> will throw later or be stored)

        qty = qty_raw

    # naive: if qty is negative, subtract; if huge, add huge amount
    current = cart.get(key, 0)
    try:
        cart[key] = current + qty
    except Exception:

        cart[key] = qty


    session['cart'] = cart

    # optionally allow next param for open redirect practice
    next_url = request.args.get('next')
    return redirect(next_url or request.referrer or url_for('index'))


@app.route('/cart/remove/<prod_id>', methods=['POST'])
def remove_from_cart(prod_id):
    cart = _get_cart()
    cart.pop(str(prod_id), None)       # remove using string key
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
        # "Process" checkout (fake)
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
    """
    INTENTIONALLY INSECURE ADMIN PANEL
    - 'Auth': trusts session['username'] equals 'admin' (hardcoded identity check).
    - SQLi: unsanitized ORDER BY and direction from query string (sort, dir).
    - Info disclosure: dumps plaintext passwords.
    - CSRF: performs state-changing actions via GET by honoring ?delete=... (&confirm=no).
    - XSS: reflects 'msg' from query into the page without escaping when used with |safe.
    """
    # 1) Weak "authorization"
    if session.get('username') != 'admin':
        # leak a bit of info about why you were blocked (verbose)
        return "Admins only. Tip: login as 'admin'.", 403

    # 2) Optional destructive action via GET (CSRF + IDOR)
    delete_user = request.args.get('delete')
    msg = ""
    if delete_user:
        try:
            conn = get_db()
            cur = conn.cursor()
            # Deliberate SQL injection risk (string formatting)
            cur.execute(f"DELETE FROM users WHERE username='{delete_user}';")
            conn.commit()
            cur.close()
            conn.close()
            msg = f"User '{delete_user}' deleted."
        except Exception as e:
            msg = f"Delete error: {e}"

    # 3) Listing users with injectable ORDER BY
    sort = request.args.get('sort', 'id')      # e.g. id, username, password
    direction = request.args.get('dir', 'ASC') # ASC or DESC
    # No whitelist… directly interpolated into SQL -> classic SQLi in ORDER BY
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

    # reflect 'msg' to demonstrate XSS if rendered with |safe in the template
    return render_template('admin.html',
                           users=users,
                           err=err,
                           msg=request.args.get('msg', msg),
                           query_used=query)


@app.route('/admin/impersonate', methods=['GET'])
def admin_impersonate():
    """
    Extra flawed helper: lets the admin (or anyone who can call it) set session.username
    via a GET parameter. Great for demonstrating session abuse.
    """
    who = request.args.get('as', 'user')
    session['username'] = who

    if who == 'user':
            return redirect(url_for('index'))

    if who == 'admin':
                return redirect(url_for('index'))

    # open redirect flavor with 'next=' param
    nxt = request.args.get('next', url_for('admin_panel'))
    return redirect(nxt)












if __name__ == '__main__':
    init_db()
    app.debug = True   # intentionally insecure for lab: shows tracebacks & secrets
    app.run(host='0.0.0.0', port=5000)
