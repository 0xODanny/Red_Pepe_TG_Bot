import json
import os
import sqlite3
from decimal import Decimal
from web3 import Web3
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

# Load environment variables from .env
load_dotenv()

# Set up global logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,  # Set to DEBUG to capture detailed logs
    handlers=[
        logging.FileHandler("output.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Example of logging a function activity
logger.info("Utilities loaded successfully.")

# Environment variables for token contract addresses and RPC URL
TOKEN_1_CONTRACT_ADDRESS = os.getenv('TOKEN_1_CONTRACT_ADDRESS')
TOKEN_2_CONTRACT_ADDRESS = os.getenv('TOKEN_2_CONTRACT_ADDRESS')
TOKEN_3_CONTRACT_ADDRESS = os.getenv('TOKEN_3_CONTRACT_ADDRESS')
AVALANCHE_RPC = os.getenv('AVALANCHE_RPC')
ROUTER_CONTRACT_ADDRESS = os.getenv('ROUTER_CONTRACT_ADDRESS')

# Initialize Web3
web3 = Web3(Web3.HTTPProvider(AVALANCHE_RPC))

# Check if Web3 is connected to the Avalanche network
if not web3.is_connected():
    logger.error("Failed to connect to Avalanche network via Web3. Check your RPC URL.")
else:
    logger.info("Successfully connected to Avalanche network via Web3.")

# Load router ABI from environment variable
ROUTER_ABI = json.loads(os.getenv('ROUTER_ABI', '[]'))
router_contract = web3.eth.contract(address=ROUTER_CONTRACT_ADDRESS, abi=ROUTER_ABI)

# SQLite Database paths
DB_PATH = 'bot_data.db'
WALLETS_DB_PATH = 'wallets.db'

# Initialize SQLite Database for bot data
def init_db():
    """Initialize the SQLite database for storing bot data."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Create the bot_data table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS bot_data (
                        chat_id TEXT,
                        user_id TEXT,
                        username TEXT,
                        last_active TEXT,
                        is_bot INTEGER,
                        PRIMARY KEY (chat_id, user_id)
                    )''')
        conn.commit()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    finally:
        conn.close()

# Save bot_data to SQLite
def save_bot_data(chat_id, user_id, username, is_bot, last_active=None):
    """Save or update user activity data in the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        if last_active is None:
            last_active = datetime.now(timezone.utc).isoformat()

        c.execute('''INSERT OR REPLACE INTO bot_data (chat_id, user_id, username, last_active, is_bot)
                     VALUES (?, ?, ?, ?, ?)''', 
                  (str(chat_id), str(user_id), username, last_active, int(is_bot)))
        conn.commit()

        logger.info(f"Bot data for {username} ({user_id}) in chat {chat_id} saved successfully.")
    except Exception as e:
        logger.error(f"Error saving bot_data: {e}")
    finally:
        conn.close()

# Load active users from SQLite within the last X hours
def get_active_users(chat_id, hours):
    """Retrieve users active in the last X hours in a specific chat."""
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=hours)
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Query for users active in the last X hours
        c.execute('''SELECT user_id, username FROM bot_data
                     WHERE chat_id = ? AND last_active >= ? AND is_bot = 0''',
                  (str(chat_id), cutoff_time.isoformat()))
        active_users = c.fetchall()

        logger.info(f"Active users in the last {hours} hours in chat {chat_id}: {active_users}")
        return active_users
    except Exception as e:
        logger.error(f"Error fetching active users: {e}")
        return []
    finally:
        conn.close()

# Clean up bot_data older than 24 hours
def clean_old_data():
    """Clean up bot activity data older than 24 hours."""
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=24)
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Delete entries older than 24 hours
        c.execute('DELETE FROM bot_data WHERE last_active < ?', (cutoff_time.isoformat(),))
        conn.commit()
        logger.info("Old bot_data entries cleaned successfully.")
    except Exception as e:
        logger.error(f"Error cleaning old bot_data: {e}")
    finally:
        conn.close()

# Wallet management functions
def get_user_wallet(user_id):
    """Retrieve a user's wallet from the SQLite database."""
    try:
        conn = sqlite3.connect(WALLETS_DB_PATH)
        c = conn.cursor()
        c.execute('SELECT address, private_key FROM wallets WHERE user_id = ?', (str(user_id),))
        wallet = c.fetchone()

        if wallet:
            logger.debug(f"Wallet found for user {user_id}")
            return {'address': wallet[0], 'private_key': wallet[1]}
        else:
            logger.info(f"No wallet found for user {user_id}")
            return None
    except Exception as e:
        logger.error(f"Error loading wallet for user {user_id}: {e}")
        return None
    finally:
        conn.close()

def save_wallet(user_id, address, private_key):
    """Save or update a user's wallet in the SQLite database."""
    try:
        conn = sqlite3.connect(WALLETS_DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO wallets (user_id, address, private_key)
            VALUES (?, ?, ?)
        ''', (str(user_id), address, private_key))
        conn.commit()

        logger.info(f"Wallet for user {user_id} saved successfully.")
    except Exception as e:
        logger.error(f"Error saving wallet for user {user_id}: {e}")
    finally:
        conn.close()

# Token contract functions
def get_token_contract(token):
    """Returns the appropriate token contract address and ABI."""
    TOKEN_ABI_TOKEN_1 = json.loads(os.getenv('TOKEN_ABI_TOKEN_1', '[]'))
    TOKEN_ABI_TOKEN_2 = json.loads(os.getenv('TOKEN_ABI_TOKEN_2', '[]'))
    TOKEN_ABI_TOKEN_3 = json.loads(os.getenv('TOKEN_ABI_TOKEN_3', '[]'))

    if token == 'token_1':
        return TOKEN_1_CONTRACT_ADDRESS, TOKEN_ABI_TOKEN_1
    elif token == 'token_2':
        return TOKEN_2_CONTRACT_ADDRESS, TOKEN_ABI_TOKEN_2
    elif token == 'token_3':
        return TOKEN_3_CONTRACT_ADDRESS, TOKEN_ABI_TOKEN_3
    else:
        logger.error(f"Unsupported token: {token}")
        raise ValueError("Unsupported token")

# Fetch token price in AVAX
def fetch_token_price_in_avax(token_address):
    """Fetches the price of a token in AVAX from the DEX router contract."""
    try:
        amount_in = Web3.to_wei(1, 'ether')  # 1 Token in wei
        amounts_out = router_contract.functions.getAmountsOut(
            amount_in, [web3.to_checksum_address(token_address), web3.to_checksum_address('0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7')]
        ).call()

        token_price_in_avax = Web3.from_wei(amounts_out[1], 'ether')
        return Decimal(token_price_in_avax)
    except Exception as e:
        logger.error(f"Error fetching token price from blockchain: {e}")
        return Decimal('0')

# Format amount based on token decimals
def format_amount(amount, token):
    """Format the amount based on the token's decimals."""
    TOKEN_DECIMALS = {
        'token_1': 2,
        'token_2': 2,
        'token_3': 2
    }
    decimals = TOKEN_DECIMALS.get(token, 2)
    return f"{amount:.{decimals}f}"

# Update leaderboard
def update_leaderboard(user_id, username, amount, action, token, filename='leaderboard.json'):
    """Update the leaderboard with user activity for specific tokens."""
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                leaderboard = json.load(f)
        else:
            leaderboard = {}

        if str(user_id) not in leaderboard:
            leaderboard[str(user_id)] = {
                'username': username,
                'token_1': {'buys': 0, 'tips': 0, 'total_spent_buys': 0.0, 'total_spent_tips': 0.0},
                'token_2': {'buys': 0, 'tips': 0, 'total_spent_buys': 0.0, 'total_spent_tips': 0.0},
                'token_3': {'buys': 0, 'tips': 0, 'total_spent_buys': 0.0, 'total_spent_tips': 0.0}
            }

        if action == 'buys':
            leaderboard[str(user_id)][token]['buys'] += 1
            leaderboard[str(user_id)][token]['total_spent_buys'] += float(amount)
        elif action == 'tips':
            leaderboard[str(user_id)][token]['tips'] += 1
            leaderboard[str(user_id)][token]['total_spent_tips'] += float(amount)

        with open(filename, 'w') as f:
            json.dump(leaderboard, f)

        logger.info("Leaderboard updated successfully.")
    except Exception as e:
        logger.error(f"Error updating leaderboard: {e}")

# Display leaderboard
def display_leaderboard(bot_data, token='token_1', filename='leaderboard.json'):
    """Display the top 10 users for buying and tipping based on the token."""
    if not os.path.exists(filename):
        return "No leaderboard data available yet."

    try:
        with open(filename, 'r') as f:
            leaderboard = json.load(f)

        top_buyers = sorted(
            [(user_id, data) for user_id, data in leaderboard.items() if data[token].get('buys', 0) > 0],
            key=lambda x: x[1][token].get('total_spent_buys', 0), reverse=True
        )[:10]

        top_tippers = sorted(
            [(user_id, data) for user_id, data in leaderboard.items() if data[token].get('tips', 0) > 0],
            key=lambda x: x[1][token].get('total_spent_tips', 0), reverse=True
        )[:10]

        def get_username(user_id):
            user_data = leaderboard.get(str(user_id), {})
            return user_data.get('username', f"User {user_id}")

        leaderboard_text = f"🏆 Top 10 {token.capitalize()} Leaderboard 🏆\n\n"
        leaderboard_text += "🔺 Top 10 Buyers:\n"
        for rank, (user_id, data) in enumerate(top_buyers, start=1):
            username = get_username(user_id)
            leaderboard_text += f"{rank}. {username}: {data[token]['buys']} buys, {format_amount(data[token].get('total_spent_buys', 0), token)} {token.upper()} spent\n"

        leaderboard_text += "\n🔺 Top 10 Tippers:\n"
        for rank, (user_id, data) in enumerate(top_tippers, start=1):
            username = get_username(user_id)
            leaderboard_text += f"{rank}. {username}: {data[token]['tips']} tips, {format_amount(data[token].get('total_spent_tips', 0), token)} {token.upper()} tipped\n"

        return leaderboard_text
    except Exception as e:
        logger.error(f"Error displaying leaderboard: {e}")
        return "Error displaying leaderboard data."