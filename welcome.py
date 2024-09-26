from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler

async def redpepebot(update: Update, context: CallbackContext) -> None:
    """
    Sends a welcome message when the /redpepebot command is issued in a private chat.
    Provides buttons to interact with common features like buying, selling, checking balances, and converting tokens.
    """
    # Check if the command is issued in a private chat
    if update.message.chat.type == 'private':
        # Welcome message text
        welcome_text = (
            "Welcome to RedPepe Bot! 🎉\n"
            "I'm here to help you with your transactions and more.\n\n"
            "You can use the following commands to get started:\n"
            "/getwallet - Create a new wallet\n"
            "/buy - Buy tokens\n"
            "/sell - Sell tokens (in private chat only)\n"
            "/tip - Tip tokens to others\n"
            "/convert - Convert between tokens\n"
            "/balance - Check your balance (in private chat only)\n"
            "/top10rpepe - Shows the top 10 buyers and tippers for rpepe\n"            
            "/top10balln - Shows the top 10 buyers and tippers for balln\n"
            "/top10nochill - Shows the top 10 buyers and tippers for nochill\n"
            "/highlow - Play a simple High Low game\n"
            "/revoke_rpepe_access - Revoke approvals for rpepe\n"
            "/cancel - Cancel the current operation\n"
        )

        # Create buttons with callback data for user interaction
        keyboard = [
            [InlineKeyboardButton("Buy Tokens", callback_data='buy')],
            [InlineKeyboardButton("Sell Tokens", callback_data='sell')],
            [InlineKeyboardButton("Check Balance", callback_data='balance')],
            [InlineKeyboardButton("Convert Tokens", callback_data='convert')],
        ]

        # Create inline keyboard markup to display buttons
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send the welcome message with the buttons in private chat
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    else:
        # Prompt the user to use private chat for this command if used in a group chat
        await update.message.reply_text("Please use this command in a private chat with me.")


async def button_handler(update: Update, context: CallbackContext) -> None:
    """
    Handles button presses from the inline keyboard in the welcome message.
    Each button corresponds to a bot function (Buy, Sell, Check Balance, Convert).
    """
    query = update.callback_query
    await query.answer()  # Acknowledge the callback

    # Handle each button based on the callback data
    if query.data == 'buy':
        await query.message.reply_text("You selected 'Buy Tokens'. Please provide the amount and token name, e.g., /buy 1 token_name.")
    elif query.data == 'sell':
        await query.message.reply_text("You selected 'Sell Tokens'. Please provide the amount and token name, e.g., /sell 1 token_name.")
    elif query.data == 'balance':
        await query.message.reply_text("You selected 'Check Balance'. Use the command /balance to see your token balances.")
    elif query.data == 'convert':
        await query.message.reply_text("You selected 'Convert Tokens'. Please provide the amount and tokens, e.g., /convert 1 token_from token_to.")