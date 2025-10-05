import os
import psycopg2
from flask import Flask, render_template, request, redirect, session, url_for

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

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
