import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT Symbol, SUM(Shares) as totalShares FROM cash WHERE id=:id GROUP BY Symbol HAVING totalShares > 0", id=session["user_id"])
    transactions=[]
    grand_total = 0
    for row in rows:
        stock = lookup(row["Symbol"])
        transactions.append({
            "Symbol": stock["symbol"],
            "Name": stock["name"],
            "Shares": row["totalShares"],
            "Price": usd(stock["price"]),
            "Total": usd(stock["price"] * row["totalShares"])
        })
        grand_total += stock["price"] * row["totalShares"]
    rows = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    cash = rows[0]["cash"]
    return render_template("table.html", transactions=transactions, cash=usd(cash), grand_total=usd(grand_total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))
        if quote is None:
            return apology("Please enter a valid symbol")
        shares = int(request.form.get("Shares"))
        if shares < 0:
            return apology("Please enter a positive value")
        shares = request.form.get("Shares")
        symbol = request.form.get("symbol")
        rows = db.execute("SELECT * FROM cash")
        cash = db.execute("SELECT * FROM cash WHERE id=:id", id=session["user_id"])

        if request.form.get("id") not in rows:
            db.execute("INSERT INTO cash (id, symbol, name, shares, cash) VALUES(:id, :symbol, :name, :shares, :cash)", id=session["user_id"], symbol=symbol, name = quote["name"], shares=shares, cash=10000)

        else:
            for row in cash:
                cash = db.execute("SELECT * FROM cash WHERE id=:id", id=session["user_id"])
                if row["Symbol"] == symbol:
                    db.execute("UPDATE cash SET shares=:shares WHERE Symbol=:Symbol", shares=cash[row]["shares"]+int(shares), Symbol=symbol)
                else:
                    db.execute("INSERT INTO cash (symbol, name, shares) VALUES(:symbol, :name, :shares)", symbol=symbol, name = quote["name"], shares=shares)

        cash = db.execute("SELECT * FROM cash WHERE id=:id", id=session["user_id"])

        current_cash = cash[0]["Cash"] - (int(shares)*int(quote["price"]))

        if current_cash > 0:
            db.execute("UPDATE cash SET cash = :cash WHERE symbol=:symbol", cash=current_cash, symbol=symbol)
            flash("Bought!")
        else:
            return apology("Not enough cash", 403)

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT Symbol, Shares, Transacted FROM cash WHERE id=:id", id=session["user_id"])
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct. check password hash is a hash function which converts the pw into a hash
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in. rows[0] is first row so rows[0]["id"] means first row, id column
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

# login required means the user must be logged in before they can see the index route
@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))
        if quote is None:
            return apology("Please enter a valid symbol")
        else:
            quote_price = quote["price"]
            quote_symbol = quote["symbol"]
            quote_name = quote["name"]
            return render_template("quoted.html", quote=quote, quote_price=quote_price, quote_symbol=quote_symbol, quote_name=quote_name)
    else:
        return render_template("quote.html")
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # ensure username is submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # ensure password is submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # ensure password entered again
        elif not request.form.get("confirm password"):
            return apology("must provide password", 403)

        # checking if username already exists
        rows = db.execute("SELECT * FROM users")

        if request.form.get("username") in rows:
            return apology("Username already taken", 403)
        elif request.form.get("password") != request.form.get("confirm password"):
            return apology("Passwords don't match", 403)
        else:
            username = request.form.get("username")
            password = generate_password_hash(request.form.get("password"))
            primary_key = db.execute("INSERT INTO users (username, hash) VALUES(:username, :password)", username = username, password = password)

            session["user_id"] = primary_key
            return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("Symbol")
        if symbol is None:
            return apology("Enter a symbol", 403)
        shares = request.form.get("Shares")
        if int(shares) < 0:
            return apology("Please enter postive shares", 403)

        stock = lookup(symbol)
        rows = db.execute("SELECT Symbol, SUM(Shares) as totalShares FROM cash WHERE id=:id GROUP BY Symbol HAVING totalShares > 0", id=session["user_id"])
        for row in rows:
            if row["Symbol"] == symbol:
                if int(shares) > row["totalShares"]:
                    return apology("Too many shares")

        rows = db.execute("SELECT Cash FROM cash WHERE id=:id", id=session["user_id"])
        cash = rows[0]["Cash"]

        current_cash = cash + int(shares)*stock["price"]
        db.execute("UPDATE cash SET Cash=:current_cash WHERE id=:id", current_cash = current_cash, id=session["user_id"])
        db.execute("INSERT INTO cash (id, Symbol, Name, Shares) VALUES (:id, :Symbol, :Name, :Shares)", id=session["user_id"], Symbol=stock["symbol"], Name=stock["name"], Shares=-1*int(shares))

        flash("Sold!")
        return redirect("/")

    else:
        rows = db.execute("SELECT Symbol FROM cash WHERE id=:id GROUP BY Symbol HAVING SUM(Shares) > 0", id=session["user_id"])
        # Shorthand for obtaining the symbol for every row in rows. So would output AAPL e.g.
        return render_template("sell.html", symbols=[ row["Symbol"] for row in rows ])


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
