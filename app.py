from flask import Flask, render_template, request, session, redirect, url_for, g
import pymysql
import bcrypt
# comments, likes
app = Flask(__name__)
app.config['SECRET_KEY'] = 'abc'
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False

connection = pymysql.connect(
    host='localhost',
    user='root',
    password='',
    db='webshop'
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

        sql = "SELECT * FROM comments WHERE product_id = %s"
        cursor.execute(sql, product_id)
        comments = [Comment(comment) for comment in cursor.fetchall()]

    if request.method == "POST" and session.get('username') is not None:
        with connection.cursor() as cursor:
            sql = "INSERT INTO `comments` (`id`, `product_id`, `author`, `content`) \
                   VALUES (NULL, %s, %s, %s);"
            cursor.execute(sql, (product_id, session['username'], request.form['content']))
            connection.commit()
            return redirect(url_for('view_product', product_id=product_id))

    return render_template('view_product.html', product=product, comments=comments)


@app.route('/product/delete_comment/<int:comment_id>', methods=['POST'])
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
