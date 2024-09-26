import logging
import atexit  # To handle bot shutdown cleanly
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, CallbackQueryHandler
from welcome import redpepebot, button_handler  # Import welcome and button handlers
from balance import check_balance  # Import balance check handler
from tip import tip  # Import tip handler for tokens
from buy import buy  # Import buy handler for tokens
from sell import sell  # Import sell handler for tokens
from convert_tokens import convert  # Token conversion handler
from utils_token import init_db, display_leaderboard, get_user_wallet, save_bot_data, clean_old_data
from rain import rain_command
from dotenv import load_dotenv
import os
from wallet import register_wallet_handlers  # Import wallet handlers

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Define conversation states
SHOW_PRIVATE_KEY = range(1)

# Configure logging to output both to console and file
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levellevel)s - %(message)s',
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler("output.log"),  # Log to file
        logging.StreamHandler()  # Log to console
    ]
)

logger = logging.getLogger(__name__)

# /commands handler
async def commands_handler(update: Update, context: CallbackContext):
    """Lists all available bot commands."""
    commands_text = (
        "/redpepebot - Start the bot and see a welcome message.\n"
        "/getwallet - Create a new wallet or show your existing one.\n"
        "/balance - Check your token balances.\n"
        "/buy <amount> <token_1> - Buy tokens with AVAX.\n"
        "/sell <amount> <token_1> - Sell tokens for AVAX.\n"
        "/tip <amount> <token_1> - Tip another user.\n"
        "/convert <amount> <from_token> <to_token> - Convert between tokens.\n"
        "/rain <amount> <token_1> <hours> - Distribute tokens to active users.\n"
        "/commands - List all available commands."
    )
    await update.message.reply_text(commands_text)

# /getwallet handler
async def getwallet(update: Update, context: CallbackContext):
    """Creates or shows a wallet, ensuring it's done in private chat."""
    if update.message.chat.type != 'private':
        await update.message.reply_text(
            "Hold on, matey! Let's not do this in public. Send this command to me privately."
        )
        return ConversationHandler.END

    user_id = str(update.message.from_user.id)
    user_wallet = get_user_wallet(user_id)  # Get user's wallet from the database

    if user_wallet:
        public_address = user_wallet['address']
        await update.message.reply_text(
            f"You already have a wallet.\n"
            f"Your wallet address: {public_address}\n"
            "Would you like to view your private key? Yes or No."
        )
        return SHOW_PRIVATE_KEY
    else:
        new_wallet = Web3().eth.account.create()
        save_wallet(user_id, new_wallet.address, new_wallet.privateKey.hex())  # Save wallet to database

        await update.message.reply_text(
            f"New wallet created!\n"
            f"Your wallet address: {new_wallet.address}\n"
            "Keep your private key safe!"
        )
        return ConversationHandler.END

# show_private_key handler
async def show_private_key(update: Update, context: CallbackContext):
    """Displays private key based on user input, if requested."""
    user_response = update.message.text.strip().lower()
    user_id = str(update.message.from_user.id)
    user_wallet = get_user_wallet(user_id)

    if user_response == 'yes' and user_wallet:
        private_key = user_wallet['private_key']
        await update.message.reply_text(
            f"Your private key: {private_key}\n"
            "Keep it safe and never share it!"
        )
        return ConversationHandler.END
    elif user_response == 'no':
        await update.message.reply_text("Operation canceled. Stay safe!")
        return ConversationHandler.END
    else:
        await update.message.reply_text("Invalid response. Please type 'Yes' or 'No'.")
        return SHOW_PRIVATE_KEY

# Handle user activity and interactions
async def user_activity_and_interaction_handler(update: Update, context: CallbackContext):
    """Logs user activity and manages interactions."""
    if update.message and update.message.from_user:
        user_id = str(update.message.from_user.id)
        username = update.message.from_user.username or f"User {user_id}"
        is_bot = update.message.from_user.is_bot

        save_bot_data(str(update.message.chat_id), user_id, username, is_bot)
        logger.info(f"User {username} ({user_id}) is active.")

# Save bot_data on shutdown
def shutdown_handler():
    logger.info("Shutting down the bot.")

def main():
    # Initialize the bot
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Initialize the SQLite database
    init_db()

    # Register wallet handlers
    register_wallet_handlers(application)

    # Add core command handlers
    application.add_handler(CommandHandler('redpepebot', redpepebot))
    application.add_handler(CommandHandler('getwallet', getwallet))
    application.add_handler(CommandHandler('balance', check_balance))
    application.add_handler(CommandHandler('buy', buy))
    application.add_handler(CommandHandler('sell', sell))
    application.add_handler(CommandHandler('tip', tip))
    application.add_handler(CommandHandler('convert', convert))

    # Add leaderboard handlers
    application.add_handler(CommandHandler('top10token1', lambda u, c: top10_token_command(u, c, 'token_1')))
    application.add_handler(CommandHandler('top10token2', lambda u, c: top10_token_command(u, c, 'token_2')))

    # Add rain handler
    application.add_handler(CommandHandler('rain', rain_command))

    # Add commands overview handler
    application.add_handler(CommandHandler('commands', commands_handler))

    # Register user activity tracking
    application.add_handler(MessageHandler(filters.ALL, user_activity_and_interaction_handler))

    # Register CallbackQueryHandlers for button handling
    application.add_handler(CallbackQueryHandler(button_handler))

    # Register wallet creation and private key management conversation handler
    wallet_handler = ConversationHandler(
        entry_points=[CommandHandler('getwallet', getwallet)],
        states={
            SHOW_PRIVATE_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_private_key)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    application.add_handler(wallet_handler)

    # Register shutdown handler to clean up resources
    atexit.register(shutdown_handler)

    # Start polling for updates
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()