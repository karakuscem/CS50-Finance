import os
import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # User ID
    user_id = session["user_id"]
    # IMPORT DATA
    userstocks = db.execute("SELECT symbol, name, price, SUM(shares) as total FROM stocktransactions WHERE user_id = ? GROUP BY symbol HAVING (SUM(shares)) > 0", user_id)
    usercash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
    totalmoney = usercash
    # CALCULATE TOTAL MONEY
    for stock in userstocks:
        totalmoney += stock["price"] * stock["total"]
    # RENDER PAGE
    return render_template("index.html", userstocks=userstocks, usercash=usercash, usd=usd, totalmoney=totalmoney)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # Show the page.
    if request.method == "GET":
        return render_template("buy.html")
    # Make user able to buy.
    else:
        # Use variables.
        stocksymbol = request.form.get("symbol")
        stock_dict = lookup(stocksymbol)
        share = int(request.form.get("shares"))
        current_price = stock_dict["price"]
        total = current_price * int(share)
        usermoney = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
        cash = usermoney[0]["cash"]
        # Check if the usage is correct.
        if not stocksymbol:
            return apology("Must provide a symbol.")
        elif not stock_dict:
            return apology("This symbol doesn't exist.")
        elif not share:
            return apology("Must provide number of shares.")
        elif int(share) < 1:
            return apology("Shares can't be negative number")
        # Check user's money is enough.
        elif (total > cash):
            return apology("Your balance is not enough")
        # Complete purchase
        date = datetime.datetime.now()
        db.execute("INSERT INTO stocktransactions (user_id, name, shares, price, type, symbol, time) VALUES(?, ?, ?, ?, ?, ?, ?)", session["user_id"], stock_dict["name"], share, current_price, "Buy", stock_dict["symbol"], date)
        # Update user's cash
        currentcash = cash - total
        db.execute("UPDATE users SET cash = ? WHERE id = ?", currentcash, session["user_id"])
        # SHOW A WARNING
        flash("Bought")
        return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # USER ID
    user_id = session["user_id"]
    # IMPORT DATA
    history = db.execute("SELECT name, shares, price, type, symbol, time FROM stocktransactions WHERE user_id = ?", user_id)
    # RENDER PAGE
    return render_template("history.html", history=history, usd=usd)

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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # If method GET show the page
    if request.method == "GET":
        return render_template("quote.html")
    # IF METHOD POST SEND
    else:
        symbol = lookup(request.form.get("symbol"))
        # CHECK CORRECT USAGE
        if symbol != None:
            return render_template("quoted.html", name=symbol["name"], symbol=symbol["symbol"], price=symbol["price"], usd=usd)
        else:
            return apology("Invalid Symbol.")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # If method GET show the page
    if request.method == "GET":
        return render_template("register.html")
    # If method POST, check right usage
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not username:
            return apology("Must provide username.")
        elif not password:
            return apology("Must provide password.")
        elif not confirmation:
            return apology("Must provide confirmation.")
        elif confirmation != password:
            return apology("Confirmation must be same with password.")

        # Store password into hash since it's more secure.
        hash = generate_password_hash(request.form.get("password"),
        method='pbkdf2:sha256', salt_length=8)

         # Query to register user to database.
        try:
            user = db.execute("INSERT INTO users (username, hash) VALUES(?, ?)",
            request.form.get("username"), hash)
            session["user_id"] = user
            return redirect("/")
        except:
            return apology("This username already taken.")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # IF METHOD IS GET SHOW PAGE
    if request.method == "GET":
        # USER ID
        user_id = session["user_id"]
        # IMPORT SYMBOLS FOR SELECT MENU
        symbols = db.execute("SELECT symbol FROM stocktransactions WHERE user_id = ? GROUP BY symbol", user_id)
        # RENDER PAGE
        return render_template("sell.html", symbols=symbols)
    # IF METHOD IS POST SEND INFO
    else:
        #USER ID, SYMBOLS, SHARES, STOCK NAME, CURRENT STOCK PRICE, OWNED STOCKS AND WORTH OF OWNED STOCKS
        user_id = session["user_id"]
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        stockname = lookup(symbol)["name"]
        stockprice = lookup(symbol)["price"]
        stockowned = db.execute("SELECT SUM(shares) FROM stocktransactions WHERE user_id = ? AND symbol = ?", user_id, symbol)[0]["SUM(shares)"]
        netprice = shares * stockprice
        # CHECK RIGHT USAGE
        if shares > stockowned:
            return apology("You don't have that much share.")
        if not symbol:
            return apology("Must choose a symbol.")
        elif not shares:
            return apology("Must provide number of shares.")
        elif shares < 1:
            return apology("Must provide positive integer of shares.")
        # SELECT USER MONEY
        usermoney = db.execute("SELECT cash FROM users WHERE id=?", user_id)
        cash = usermoney[0]["cash"]
        # UPDATE USER MONEY
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash + netprice, user_id)
        # UPDATE DATABASE
        date = datetime.datetime.now()
        db.execute("INSERT INTO stocktransactions (user_id, name, shares, price, type, symbol, time) VALUES(?, ?, ?, ?, ?, ?, ?)", user_id, stockname, -shares, stockprice, "Sell", symbol, date)
        # SHOW WARNING
        flash("Sold")
        return redirect("/")
