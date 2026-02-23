import difflib
import getpass
from random import choice
import requests
from colorama import Fore, Style, init
init()
getgamesplayed = 0
SERVER_URL = "https://homoeomorphic-consumedly-launa.ngrok-free.dev" 
money = 0
password_cache = ''
token_cache = ''
username = ''
def refresh_money():
    global money
    try:
        r = requests.post(f"{SERVER_URL}/login", json={
            "username": username,
            "password": password_cache
        }).json()
        if r.get("success"):
            money = r["money"]
    except Exception as e:
        print("Failed to refresh money:", e)

# Get leaderboard
def get_leaderboard():
    global username, money, getgamesplayed
    try:
        r = requests.get(f"{SERVER_URL}/leaderboard", timeout=3)
        data = r.json()
        
        # mark the current user for client highlighting
        for entry in data.get("leaderboard", []):
            if entry["username"] == username:
                entry["highlight"] = True
            else:
                entry["highlight"] = False
        return data
    except:
        print(Fore.RED + "Failed to retrieve leaderboard. Server might be down." + Style.RESET_ALL)
        return {
            "leaderboard": [{"username": username, "money": money, "highlight": True}]
        }

def face_down():
    return Fore.RED + "🂠" + Style.RESET_ALL
def get_money():
    """
    Logs in a user or creates a new account on the server.
    Returns (username, money, gamesplayed) or False on failure.
    """
    global username, money, getgamesplayed,password_cache,token_cache
    username = input("Enter your username: ")
    password = getpass.getpass("Insert password: ")

    # Attempt login
    try:
        r = requests.post(f"{SERVER_URL}/login", json={
            "username": username,
            "password": password
        }).json()
    except:
        print("Failed to connect to server. Using local account as fallback.")
        money = 1000
        return True
    if r["success"]:
        password_cache = password
        money = r["money"]
        getgamesplayed = r["gamesplayed"]
        token_cache = r["token"]  # store the token
        return True
    else:
        if r["error"] == "Username not found":
            password = getpass.getpass("No account found. Set a password to create account: ")
            r = requests.post(f"{SERVER_URL}/create_account", json={
                "username": username,
                "password": password
            }).json()
            if r["success"]:
                password_cache = password
                money = 1000
                getgamesplayed = 0
                return True
        print(r.get("error", "Login failed"))
        return False
def color_card(card):
    suit = card[-1]
    if suit in ['♥', '♦']:
        return Fore.RED + card + Style.RESET_ALL
    else:
        return Fore.WHITE + card + Style.RESET_ALL

def format_cards(cards):
    return " ".join(color_card(card) for card in cards)


def blackjack():
    global username, money, token_cache

    bet = input("How much money are you betting? or type 'q' to quit: ")

    if bet == 'q':
        return True

    try:
        bet = int(bet)
        if bet > 2000 or bet <50:
            print('The max range is 50-1000!')
            return None
        elif bet > money*0.5:
            checkup = input("You're betting more than half your money! Press enter to confirm or press q to cancel")
            if checkup == 'q':
                return None
    except:
        print("Invalid Response. Must be a number.")
        return None

    r = requests.post(f"{SERVER_URL}/start_blackjack", json={
        "username": username,
        "bet": bet,
        "token": token_cache  # include token
    }).json()
    if "token" in r:
        token_cache = r["token"]

    if not r.get("success"):
        print(r.get("error"))
        return None

    player = r["player"]
    dealer = r["dealer"]

    print("\nDealer:", dealer)
    print("You:", player, f"(total {r['player_total']})")

    # Player turn loop
    while True:
        choices = ["hit", "stand", "double"]
        response = input("hit,stand, or double: ").lower()
        action = difflib.get_close_matches(response, choices, n=1, cutoff=0.3)
        if not action:
            print("Invalid action.")
            continue
        r = requests.post(f"{SERVER_URL}/blackjack_action", json={
            "username": username,
            "action": action[0],
            "token": token_cache  # include token
        }).json()
        if "token" in r:
            token_cache = r["token"]

        if r.get("error"):
            print(r["error"])
            continue

        # If result exists, game ended
        if "result" in r:
            print("\nFinal Hands:")
            print("Dealer:", r["dealer"])
            print("You:", r["player"])

            print("Result:", r["result"])

            if "money" in r:
                money = r["money"]
                print("New balance:", money)

            return None

        # Otherwise still player turn
        print("\nDealer:", r["dealer"])
        print("You:", r["player"], f"(total {r['player_total']})")
quit = False
if not get_money():
    print('Invalid login. Closing game.')
    quit = True
else:
    print(f'Logged in as {username}:')
    print('    Account balance: $' + str(money))
    print('    games played: ' + str(getgamesplayed))
while True:
    if quit == True:
        break
    userchoices = ['blackjack','quit','leaderboard']
    print(userchoices)
    userwant = input('What would you like to do?  ')
    useraction = difflib.get_close_matches(userwant,userchoices,n=1,cutoff = 0.3)
    if not useraction:
        print('invalid response')
        continue
    if useraction[0] == 'blackjack':
        while True:
            print(f"\nYou have ${money}")
            if blackjack() == True:
                break
            if money == 0:
                print(Fore.RED + Style.BRIGHT + "You ran out of money!" + Style.RESET_ALL)
                quit = True
                break
            else:
                continue
    elif useraction[0] == 'leaderboard':
        leaderboard = get_leaderboard()
        print("\n🏆 Leaderboard 🏆")
        for entry in leaderboard["leaderboard"]:
            print(f"  {entry['username']}: ${entry['money']}")
    elif useraction[0] == 'quit':
        break
