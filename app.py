import functools
import os
from flask import Flask, render_template, request, session, redirect, url_for, g, abort
import pymysql
import bcrypt

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('secret_key') or 'abc'
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False

connection = pymysql.connect(
    host=os.environ.get('db_host') or 'localhost',
    user=os.environ.get('db_username') or 'root',
    password=os.environ.get('db_password') or '',
    db=os.environ.get('db_database') or 'Webshop'
)


class Product:
    def __init__(self, line):
        self.id = line[0]
        self.name = line[1]
        self.price = line[2]

    def todict(self):
        return {
            'name': self.name,
            'price': self.price,
        }


class Comment:
    def __init__(self, line):
        self.id = line[0]
        self.product_id = line[1]
        self.author = line[2]
        self.content = line[3]
        self.date = line[4]


def fully_authenticated(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))

        return view(**kwargs)

    return wrapped_view


def load_products():
    with connection.cursor() as cursor:
        sql = "SELECT * FROM products;"
        cursor.execute(sql)
        results = cursor.fetchall()

    products = []
    for result in results:
        products.append(Product(result))
    return products


def handle_cart(product_object, quantity):
    product_object.id = str(product_object.id)
    if product_object.id not in session['cart'].keys():
        session['cart'][product_object.id] = {'product': product_object.todict(), 'quantity': quantity}
    else:
        current_quantity = session['cart'][product_object.id]['quantity']
        session['cart'][product_object.id] = {'product': product_object.todict(),
                                              'quantity': current_quantity + quantity}


@app.before_request
def create_cart():
    session['cart'] = session.get('cart', {})


@app.before_request
def load_current_user():
    if session.get('username') is not None:
        g.user = {'username': session['username']}
    else:
        g.user = None


@app.route('/', methods=['GET', 'POST'])
def index():
    products = load_products()
    if request.method == 'POST':
        if request.form.get('clear_cart') is not None:
            del session['cart']
            return redirect(url_for('index'))
        product_id = int(request.form['product_id'])
        quantity = int(request.form['quantity'])

        with connection.cursor() as cursor:
            sql = "SELECT * FROM products WHERE id = %s"
            cursor.execute(sql, product_id)
            result = Product(cursor.fetchone())
            handle_cart(result, quantity)
        return redirect(url_for('index'))

    return render_template('index.html', products=products)


@app.route('/product/<int:product_id>', methods=['GET', 'POST'])
def view_product(product_id):
    with connection.cursor() as cursor:
        sql = "SELECT * FROM products WHERE id = %s"
        cursor.execute(sql, product_id)
        product = Product(cursor.fetchone())

        sql = "SELECT * FROM comments WHERE product_id = %s ORDER BY datetime"
        cursor.execute(sql, product_id)
        comments = [Comment(comment) for comment in cursor.fetchall()]

        sql = "SELECT like_id FROM likes WHERE product_id = %s"
        cursor.execute(sql, product_id)
        likes = len(cursor.fetchall())

    if request.method == "POST" and session.get('username') is not None and 'content' in request.form:
        with connection.cursor() as cursor:
            sql = "INSERT INTO `comments` (`id`, `product_id`, `author`, `content`) \
                   VALUES (NULL, %s, %s, %s);"
            cursor.execute(sql, (product_id, session['username'], request.form['content']))
            connection.commit()
            return redirect(url_for('view_product', product_id=product_id))

    return render_template('view_product.html', product=product, comments=comments, likes=likes,
                           liked=is_it_liked_by_user(product_id))


@app.route('/product/delete_comment/<int:comment_id>', methods=['POST'])
@fully_authenticated
def delete_comment(comment_id):
    with connection.cursor() as cursor:
        sql = "SELECT product_id, author FROM comments WHERE id = %s"
        cursor.execute(sql, comment_id)
        result = cursor.fetchone()
        if result[1] == session['username']:
            sql = "DELETE FROM `comments` WHERE id = %s;"
            cursor.execute(sql, comment_id)
            connection.commit()
    return redirect(url_for('view_product', product_id=result[0]))


def is_it_liked_by_user(product_id):
    with connection.cursor() as cursor:
        sql = "SELECT author FROM likes WHERE product_id = %s"
        cursor.execute(sql, product_id)
        try:
            authors = cursor.fetchall()
            if 'username' in session:
                for author in authors:
                    if session['username'] in author[0]:
                        return True
                return False
        except IndexError:
            return False


@app.route('/product/like/<int:product_id>', methods=['POST'])
@fully_authenticated
def like(product_id):
    # like
    if request.form.get('like_button', 'off') == 'on' and not is_it_liked_by_user(product_id):
        with connection.cursor() as cursor:
            sql = "INSERT INTO likes (like_id, product_id, author) VALUES (NULL, %s, %s)"
            cursor.execute(sql, (product_id, session['username']))
            connection.commit()
    # remove like
    elif request.form.get('like_button', 'off') == 'off' and is_it_liked_by_user(product_id):
        with connection.cursor() as cursor:
            sql = "DELETE FROM likes WHERE product_id = %s AND author = %s"
            cursor.execute(sql, (product_id, session['username']))
            connection.commit()

    return redirect(url_for('view_product', product_id=product_id))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        with connection.cursor() as cursor:
            sql = "INSERT INTO `users` (`username`, `password`, `role`) VALUES (%s, %s, %s);"
            cursor.execute(sql, (username, hashed, 'user'))
            connection.commit()
            session.clear()
            session['username'] = username
            return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with connection.cursor() as cursor:
            sql = "SELECT password FROM users WHERE username = %s;"
            cursor.execute(sql, username)
            hashed = cursor.fetchone()[0]
            if bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8')):
                session.clear()
                session['username'] = request.form['username']
                return redirect(url_for('index'))

    return render_template("login.html")


@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run()
