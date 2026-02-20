from flask import Flask, request, jsonify
import hashlib
import time
import json
import os
import random
import secrets
from colorama import Fore, Style, init
init()

app = Flask(__name__)
accountfile = r"/workspaces/codespaces-blank/blackjack/accounts.json"

tokens = {}
token_time = 300

def load_accounts():
    global accounts
    if os.path.exists(accountfile):
        with open(accountfile, "r") as f:
            accounts = json.load(f)
    else:
        accounts = {}

active_games = {} 



def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def save_accounts():
    with open(accountfile, "w") as f:
        json.dump(accounts, f, indent=4)

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

    if username in accounts:
        return jsonify({"success": False, "error": "Username exists"})

    accounts[username] = {
        "password": hash_password(password),
        "money": 1000,
        "gamesplayed": 0
    }
    save_accounts()
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
def login():
    load_accounts()
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if username not in accounts:
        return jsonify({"success": False, "error": "Username not found"})

    if accounts[username]["password"] != hash_password(password):
        return jsonify({"success": False, "error": "Incorrect password"})

    token = generate_token(username)

    return jsonify({
        "success": True,
        "money": accounts[username]["money"],
        "gamesplayed": accounts[username].get("gamesplayed", 0),
        "token": token
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

        if username not in accounts:
            return jsonify({"success": False, "error": "Invalid user"})

        if bet <= 0 or bet > accounts[username]["money"]:
            return jsonify({"success": False, "error": "Invalid bet"})

        deck = new_deck()
        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]

        accounts[username]["money"] -= bet
        token_new = generate_token(username)  # <- make sure username is passed
        accounts[username]["gamesplayed"] += 1

        active_games[username] = {
            "deck": deck,
            "player": player,
            "dealer": dealer,
            "bet": bet,
            "finished": False
        }

        save_accounts()

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
            save_accounts()
            return jsonify({
                "result": result,
                "player": player,
                "dealer": dealer,
                "player_total": player_total,
                "dealer_total": dealer_total,
                "money": accounts[username]["money"],
                "token": tokens[username]["token"]
            })

        return jsonify({
            "player": player,
            "dealer": [dealer[0], "🂠"],
            "player_total": player_total,
            "token": tokens[username]["token"]
        })

    # STAND
    if action == "stand":
        while hand_value(dealer) < 17:
            dealer.append(deck.pop())

        player_total = hand_value(player)
        dealer_total = hand_value(dealer)

        result = ""
        if dealer_total > 21 or player_total > dealer_total:
            accounts[username]["money"] += bet * 2
            tokens[username] = {"token": generate_token(username), "time": time.time()} 
            result = Fore.GREEN + "win" + Style.RESET_ALL
        elif dealer_total == player_total:
            accounts[username]["money"] += bet
            tokens[username] = {"token": generate_token(username), "time": time.time()} 
            result = Fore.YELLOW + "push" + Style.RESET_ALL
        else:
            result = Fore.RED + "lose" + Style.RESET_ALL
            tokens[username] = {"token": generate_token(username), "time": time.time()} 

        game["finished"] = True
        save_accounts()

        return jsonify({
            "result": result,
            "player": player,
            "dealer": dealer,
            "player_total": player_total,
            "dealer_total": dealer_total,
            "money": accounts[username]["money"],
           "token": tokens[username]["token"]
        })

    return jsonify({"success": False, "error": "Invalid action"})

# ----------------------------
# LEADERBOARD
# ----------------------------

@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    sorted_accounts = sorted(accounts.items(),
                             key=lambda x: x[1]["money"],
                             reverse=True)

    top = [{"username": u, "money": d["money"]}
           for u, d in sorted_accounts[:5]]

    return jsonify({"leaderboard": top})

# ----------------------------

if __name__ == "__main__":
    app.run(debug=True)