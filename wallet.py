import logging
import sqlite3
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler, CommandHandler, MessageHandler, filters
from web3 import Web3
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Configure logging to log to file and console
logging.basicConfig(
    filename='output.log',
    level=logging.DEBUG,    
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  
    filemode='w'  # Overwrite the log file each time (use 'a' to append)
)
logger = logging.getLogger(__name__)

# Get environment variables
RPC_URL = os.getenv('AVALANCHE_RPC')

# Connect to the blockchain network (generalized as RPC_URL)
web3 = Web3(Web3.HTTPProvider(RPC_URL))

# Define conversation states
SHOW_PRIVATE_KEY = range(1)

# SQLite database path for storing wallets
WALLETS_DB_PATH = 'wallets.db'

# Function to retrieve a wallet from the SQLite database
def get_user_wallet(user_id):
    """Retrieve a user's wallet (public and private keys) from the SQLite database."""
    try:
        conn = sqlite3.connect(WALLETS_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT address, private_key FROM wallets WHERE user_id = ?", (user_id,))
        wallet = c.fetchone()
        conn.close()
        logger.debug(f"Fetched wallet for user {user_id}: {wallet}")
        if wallet:
            return {'address': wallet[0], 'private_key': wallet[1]}
        return None
    except Exception as e:
        logger.error(f"Error retrieving wallet for user {user_id}: {e}")
        return None

# Function to save a wallet to the SQLite database
def save_user_wallet(user_id, address, private_key):
    """Save or update a user's wallet (public and private keys) in the SQLite database."""
    try:
        conn = sqlite3.connect(WALLETS_DB_PATH)
        c = conn.cursor()
        logger.debug(f"Saving wallet for user {user_id}: {address}")
        c.execute('''
            INSERT OR REPLACE INTO wallets (user_id, address, private_key)
            VALUES (?, ?, ?)
        ''', (user_id, address, private_key))
        conn.commit()
        conn.close()
        logger.info(f"Wallet for user {user_id} saved successfully.")
    except Exception as e:
        logger.error(f"Error saving wallet for user {user_id}: {e}")

# /getwallet command handler
async def getwallet(update: Update, context: CallbackContext) -> int:
    """Handles the /getwallet command to create or show an existing wallet."""
    user_id = str(update.message.from_user.id)  # Get the user ID
    chat_type = update.message.chat.type  # Determine if the chat is private or public

    # Ensure the command is only used in private chat
    if chat_type != 'private':
        await update.message.reply_text(
            "Ahoj matey, don't use this command aboard for all eyes to see!\n"
            "Please send this command in a private chat with me to see your wallet details."
        )
        return ConversationHandler.END

    # Retrieve the user's wallet, if it exists
    user_wallet = get_user_wallet(user_id)

    if user_wallet:
        # If the wallet exists, ask if the user wants to see the private key
        public_address = user_wallet['address']
        logger.debug(f"User {user_id} already has a wallet. Asking about private key.")
        await update.message.reply_text(
            f"You already have a wallet, my friend.\n"
            f"Your wallet address: {public_address}\n"
            "Would you like to view your private key? Type 'yes' or 'no'."
        )
        return SHOW_PRIVATE_KEY  # Move to the state to handle the user's response
    else:
        try:
            # If no wallet exists, create a new one
            new_wallet = web3.eth.account.create()
            save_user_wallet(user_id, new_wallet.address, new_wallet.key.hex())

            logger.debug(f"New wallet created for user {user_id}")
            await update.message.reply_text(
                f"New wallet created!\n"
                f"Your wallet address: {new_wallet.address}\n"
                "Keep your private key safe!"
            )
        except Exception as e:
            logger.error(f"Error creating wallet for user {user_id}: {e}")
            await update.message.reply_text("An error occurred while creating your wallet. Please try again later.")

        return ConversationHandler.END

# Handler to display the private key if the user opts in
async def show_private_key(update: Update, context: CallbackContext) -> int:
    """Handles showing the private key based on user response."""
    user_response = update.message.text.strip().lower()  # Normalize user input
    user_id = str(update.message.from_user.id)
    user_wallet = get_user_wallet(user_id)

    if user_response in ['yes', 'y'] and user_wallet:
        # If the user said 'yes' and a wallet exists, show the private key
        private_key = user_wallet['private_key']
        logger.debug(f"Displaying private key for user {user_id}")
        await update.message.reply_text(
            f"Your private key is: {private_key}\n"
            "Keep it safe and do not share it with anyone!"
        )
        return ConversationHandler.END
    elif user_response in ['no', 'n']:
        # If the user said 'no', exit the conversation
        logger.debug(f"User {user_id} canceled viewing the private key.")
        await update.message.reply_text("Operation canceled. Stay safe!")
        return ConversationHandler.END
    else:
        # If the user input is invalid, ask again
        logger.debug(f"Invalid response from user {user_id}: {user_response}")
        await update.message.reply_text("Invalid response. Please type 'yes' or 'no'.")
        return SHOW_PRIVATE_KEY  # Remain in this state until a valid response is received

# /cancel command handler to exit the conversation
async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancels the conversation."""
    logger.debug(f"User {update.message.from_user.id} canceled the operation.")
    await update.message.reply_text("Operation canceled.")
    return ConversationHandler.END

# Register wallet-related handlers in the bot
def register_wallet_handlers(application):
    """Registers the wallet creation and private key handlers."""
    wallet_handler = ConversationHandler(
        entry_points=[CommandHandler('getwallet', getwallet)],
        states={
            SHOW_PRIVATE_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_private_key)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    application.add_handler(wallet_handler)