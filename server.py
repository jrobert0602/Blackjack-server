from flask import Flask, request, jsonify
import hashlib
import time
import os
import random
import secrets
import sqlite3
from colorama import Fore, Style, init
init()
app = Flask(__name__)
BASE_DIR = os.path.dirname(__file__)
DB_FILE = os.path.join(BASE_DIR, "casino.db")
tokens = {}
token_time = 300



active_games = {} 

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        money INTEGER NOT NULL,
        games_played INTEGER NOT NULL
    )
    """)
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def new_deck():
    deck = ['A♠','2♠','3♠','4♠','5♠','6♠','7♠','8♠','9♠','10♠','J♠','Q♠','K♠',
            'A♥','2♥','3♥','4♥','5♥','6♥','7♥','8♥','9♥','10♥','J♥','Q♥','K♥',
            'A♦','2♦','3♦','4♦','5♦','6♦','7♦','8♦','9♦','10♦','J♦','Q♦','K♦',
            'A♣','2♣','3♣','4♣','5♣','6♣','7♣','8♣','9♣','10♣','J♣','Q♣','K♣'] * 6
    random.shuffle(deck)
    return deck

def hand_value(cards):
    total = 0
    aces = 0
    for c in cards:
        val = c[:-1]
        if val in ['J','Q','K']:
            total += 10
        elif val == 'A':
            total += 11
            aces += 1
        else:
            total += int(val)

    while total > 21 and aces > 0:
        total -= 10
        aces -= 1

    return total


@app.route("/create_account", methods=["POST"])
def create_account():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "error": "Username exists"})

    cursor.execute("""
        INSERT INTO users (username, password_hash, money, games_played)
        VALUES (?, ?, ?, ?)
    """, (username, hash_password(password), 1000, 0))

    conn.commit()
    conn.close()

    return jsonify({"success": True})
def generate_token(username):
    token = secrets.token_hex(32)
    tokens[username] = {"token": token, "time": time.time()}
    return token
def check_token(username, token):
    data = tokens.get(username)
    if not data or data["token"] != token:
        return False
    if time.time() - data["time"] > token_time:
        del tokens[username]
        return False
    return True
@app.route("/login", methods=["POST"])
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"success": False, "error": "Username not found"})

    if user["password_hash"] != hash_password(password):
        conn.close()
        return jsonify({"success": False, "error": "Incorrect password"})

    # --- DAILY LOGIN BONUS ---
    now = int(time.time())
    last_daily = user["last_daily"] if "last_daily" in user.keys() else 0
    bonus_given = 0
    if now - last_daily >= 24*60*60:  # 24 hours passed
        bonus_given = 100
        cursor.execute(
            "UPDATE users SET money = money + ?, last_daily = ? WHERE username = ?",
            (bonus_given, now, username)
        )
        conn.commit()
    # -------------------------

    token = generate_token(username)

    conn.close()

    return jsonify({
        "success": True,
        "money": user["money"] + bonus_given,  # show updated money
        "gamesplayed": user["games_played"],
        "token": token,
        "daily_bonus": bonus_given
    })



@app.route("/start_blackjack", methods=["POST"])
def start_blackjack():
    try:
        data = request.json
        username = data.get("username")
        token = data.get("token")
        bet = int(data.get("bet", 0))

        if not check_token(username, token):
            return jsonify({"success": False, "error": "Invalid or expired token"})

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT money FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if not user:
            conn.close()
            return jsonify({"success": False, "error": "Invalid user"})

        if bet <= 0 or bet > user["money"]:
            conn.close()
            return jsonify({"success": False, "error": "Invalid bet"})
        elif bet > 2000 or bet < 50:
            conn.close()
            return jsonify({"success": False,"error": "Exceeds min/max range of 50-2000" })

        conn.execute("UPDATE users SET money = money - ?, games_played = games_played + 1 WHERE username = ?", (bet, username))
        conn.commit()
        conn.close()

        deck = new_deck()
        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]

        token_new = generate_token(username)  # <- make sure username is passed

        active_games[username] = {
            "deck": deck,
            "player": player,
            "dealer": dealer,
            "bet": bet,
            "finished": False,
            "blackjack_bonus" : 0.5 if hand_value(player) == 21 else 0
        }
        if hand_value(player) == 21:
            game = active_games[username]
            conn = get_db()
            conn.execute(
                "UPDATE users SET money = money + ? WHERE username = ?",
                (bet * (2 + game["blackjack_bonus"]), username)
            )
            conn.commit()
            conn.close()
            game["finished"] = True
        return jsonify({
            "success": True,
            "player": player,
            "dealer": [dealer[0], "HIDDEN"],
            "player_total": hand_value(player),
            "token": token_new   # use this variable
        })
    except Exception as e:
        print("Error in start_blackjack:", e)
        return jsonify({"success": False, "error": "Server error"})
def ifsoft(hand):
    total = 0
    aces = 0

    for c in hand:
        val = c[:-1]
        if val in ['J','Q','K']:
            total += 10
        elif val == 'A':
            total += 11
            aces += 1
        else:
            total += int(val)

    # downgrade aces if busting
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1

    # soft 17 = total is 17 and at least one ace still counted as 11
    return total == 17 and aces > 0
@app.route("/blackjack_action", methods=["POST"])
def blackjack_action():
    data = request.json
    username = data.get("username")
    token = data.get("token")
    action = data.get("action")

    if username not in active_games:
        return jsonify({"success": False, "error": "No active game"})

    if not check_token(username, token):
        return jsonify({"success": False, "error": "Invalid or expired token"})
    game = active_games[username]

    if game["finished"]:
        return jsonify({"success": False, "error": "Game already finished"})

    deck = game["deck"]
    player = game["player"]
    dealer = game["dealer"]
    bet = game["bet"]

    # HIT
    if action == "hit":
        player.append(deck.pop())
        player_total = hand_value(player)
        if player_total > 21:
            game["finished"] = True
            dealer_total = hand_value(dealer)
            result = Fore.RED + "bust" + Style.RESET_ALL
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT money FROM users WHERE username = ?", (username,))
            money = cursor.fetchone()["money"]
            conn.close()
            return jsonify({
                "result": result,
                "player": player,
                "dealer": dealer,
                "player_total": player_total,
                "dealer_total": dealer_total,
                "money": money,
                "token": tokens[username]["token"]
            })

        return jsonify({
            "player": player,
            "dealer": [dealer[0], "🂠"],
            "player_total": player_total,
            "token": tokens[username]["token"]
        })
    elif action == "double":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT money FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        if len(player) != 2 or bet > user["money"]:
            return jsonify({"success": False, "error": "Cannot double"})
        conn = get_db()
        conn.execute("UPDATE users SET money = money - ? WHERE username = ?", (bet, username))
        conn.commit()
        conn.close()

        game["bet"] *= 2
        player.append(deck.pop())
        player_total = hand_value(player)
        if player_total > 21:
            game["finished"] = True
            dealer_total = hand_value(dealer)
            result = Fore.RED + "bust" + Style.RESET_ALL
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT money FROM users WHERE username = ?", (username,))
            money = cursor.fetchone()["money"]
            conn.close()
            action = "stand"
            return jsonify({
                "result": result,
                "player": player,
                "dealer": dealer,
                "player_total": player_total,
                "dealer_total": dealer_total,
                "money": money,
                "token": tokens[username]["token"]
            })
    # STAND
    if action == "stand":
        while hand_value(dealer) < 17 or ifsoft(dealer):
            dealer.append(deck.pop())

        player_total = hand_value(player)
        dealer_total = hand_value(dealer)

        result = ""
        if dealer_total > 21 or player_total > dealer_total:  # win
            conn = get_db()
            conn.execute("UPDATE users SET money = money + ? WHERE username = ?", (bet * (2+game["blackjack_bonus"]), username))
            conn.commit()
            conn.close()
            result = Fore.GREEN + "win" + Style.RESET_ALL
        elif dealer_total == player_total:  # push
            conn = get_db()
            conn.execute("UPDATE users SET money = money + ? WHERE username = ?", (bet, username))
            conn.commit()
            conn.close()
            result = Fore.YELLOW + "push" + Style.RESET_ALL
        # lose → do nothing (already subtracted) 
        else:
            result = Fore.RED + "lose" + Style.RESET_ALL
        game["finished"] = True
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT money FROM users WHERE username = ?", (username,))
        money = cursor.fetchone()["money"]
        conn.close()
        return jsonify({
            "result": result,
            "player": player,
            "dealer": dealer,
            "player_total": player_total,
            "dealer_total": dealer_total,
            "money": money,
           "token": tokens[username]["token"]
        })

    return jsonify({"success": False, "error": "Invalid action"})

# ----------------------------
# LEADERBOARD
# ----------------------------

@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    username = request.args.get("username")  # get username from query

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT username, money
        FROM users
        ORDER BY money DESC
        LIMIT 5
    """)

    top = []
    for row in cursor.fetchall():
        entry = {"username": row["username"], "money": row["money"]}
        if row["username"] == username:
            entry["highlight"] = True  # mark this user
        top.append(entry)

    conn.close()
    return jsonify({"leaderboard": top})
# ----------------------------

if __name__ == "__main__":
    init_db()
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_daily INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.close()
    app.run(host="0.0.0.0", port=5000, debug=True)