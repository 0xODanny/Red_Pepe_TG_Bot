import logging
from decimal import Decimal
from telegram import Update
from telegram.ext import CallbackContext
from web3 import Web3
from web3.middleware import geth_poa_middleware
from dotenv import load_dotenv
import os
import json
from utils_token import get_user_wallet, update_leaderboard

# Load environment variables from .env
load_dotenv()

# Get environment variables
AVALANCHE_RPC = os.getenv('AVALANCHE_RPC')

# Connect to Avalanche
web3 = Web3(Web3.HTTPProvider(AVALANCHE_RPC))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to dynamically select the token contract and ABI
def get_token_contract(token):
    """Returns the appropriate token contract address and ABI based on the token name."""
    token_contract_address = os.getenv(f'{token.upper()}_TOKEN_CONTRACT_ADDRESS')
    token_abi = json.loads(os.getenv(f'TOKEN_ABI_{token.upper()}', '[]'))

    if token_contract_address and token_abi:
        return token_contract_address, token_abi
    else:
        raise ValueError("Unsupported or unknown token")

async def tip(update: Update, context: CallbackContext) -> None:
    """Handles the /tip command to tip users with tokens."""
    
    if len(context.args) != 2:
        await update.message.reply_text('Usage: /tip <amount> <token>')
        return

    try:
        # Parse amount and token
        amount = float(context.args[0])
        token = context.args[1].lower()

        # Load sender's wallet from the database
        user_id = str(update.message.from_user.id)
        username = update.message.from_user.username or f"User {user_id}"
        user_wallet = get_user_wallet(user_id)

        if not user_wallet:
            await update.message.reply_text("You don't have a wallet yet. Use /getwallet to create one.")
            return

        user_wallet_address = user_wallet['address']
        user_private_key = user_wallet['private_key']

        # Ensure the command is a reply to the recipient's message
        if not update.message.reply_to_message:
            await update.message.reply_text('You need to reply to the user you want to tip.')
            return

        # Get recipient's wallet
        recipient_id = str(update.message.reply_to_message.from_user.id)
        recipient_wallet = get_user_wallet(recipient_id)

        if not recipient_wallet:
            await update.message.reply_text("The recipient doesn't have a wallet yet. Ask them to use /getwallet.")
            return

        recipient_wallet_address = recipient_wallet['address']

        # Handle AVAX transfer
        if token == 'avax':
            avax_balance_wei = web3.eth.get_balance(user_wallet_address)
            avax_amount_wei = web3.to_wei(amount, 'ether')

            if avax_balance_wei < avax_amount_wei:
                await update.message.reply_text("You don't have enough AVAX to tip.")
                return

            # Prepare AVAX transfer transaction
            avax_txn = {
                'from': web3.to_checksum_address(user_wallet_address),
                'to': web3.to_checksum_address(recipient_wallet_address),
                'value': avax_amount_wei,
                'gas': 21000,
                'gasPrice': web3.to_wei('50', 'gwei'),
                'nonce': web3.eth.get_transaction_count(user_wallet_address),
                'chainId': 43114  # Avalanche C-Chain ID
            }

            # Sign and send the AVAX transaction
            signed_avax_txn = web3.eth.account.sign_transaction(avax_txn, private_key=user_private_key)
            raw_avax_txn = signed_avax_txn.rawTransaction
            avax_tx_hash = web3.eth.send_raw_transaction(raw_avax_txn)

            # Log and inform the user
            logger.info(f"AVAX tip transaction sent: {avax_tx_hash.hex()}")
            snowtrace_link = f"https://snowtrace.io/tx/{avax_tx_hash.hex()}"
            await update.message.reply_text(
                f"AVAX tip sent successfully! [Snowtrace transaction link]({snowtrace_link})",
                parse_mode='Markdown'
            )
            return

        # For ERC-20 tokens, validate the token and perform transfer
        token_contract_address, token_abi = get_token_contract(token)

        # Check user's token balance
        token_contract = web3.eth.contract(address=token_contract_address, abi=token_abi)
        token_balance = token_contract.functions.balanceOf(user_wallet_address).call()

        if token_balance < Web3.to_wei(amount, 'ether'):
            await update.message.reply_text("You don't have enough tokens to tip.")
            return

        # Prepare the ERC-20 token transfer transaction
        tip_txn = token_contract.functions.transfer(
            recipient_wallet_address,
            Web3.to_wei(amount, 'ether')
        ).build_transaction({
            'from': user_wallet_address,
            'gas': 200000,
            'gasPrice': web3.to_wei('50', 'gwei'),
            'nonce': web3.eth.get_transaction_count(user_wallet_address),
            'chainId': 43114  # Avalanche C-Chain ID
        })

        # Sign and send the ERC-20 token transaction
        signed_tip_txn = web3.eth.account.sign_transaction(tip_txn, private_key=user_private_key)
        raw_tip_txn = signed_tip_txn.rawTransaction
        tip_tx_hash = web3.eth.send_raw_transaction(raw_tip_txn)

        # Log and inform the user
        logger.info(f"Tip transaction sent: {tip_tx_hash.hex()}")
        snowtrace_link = f"https://snowtrace.io/tx/0x{tip_tx_hash.hex()}"
        await update.message.reply_text(
            f"Tip sent successfully! [Snowtrace transaction link]({snowtrace_link})",
            parse_mode='Markdown'
        )

        # Update the leaderboard with the tip
        update_leaderboard(user_id, username, amount, 'tips', token)

    except Exception as e:
        logger.error(f'An error occurred while trying to tip {token.upper()}: {e}')
        await update.message.reply_text(f'An error occurred while trying to tip {token.upper()}: {e}')