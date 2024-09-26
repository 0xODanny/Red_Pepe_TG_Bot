import logging
from telegram import Update
from telegram.ext import CallbackContext
from decimal import Decimal
from utils_token import get_user_wallet  # Only import get_user_wallet now
from dotenv import load_dotenv
import os
import json
from web3 import Web3
from web3.middleware import geth_poa_middleware
import requests
import time

# Load environment variables from .env file
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Get environment variables
ROUTER_CONTRACT_ADDRESS = os.getenv('ROUTER_CONTRACT_ADDRESS')
ROUTER_ABI = json.loads(os.getenv('ROUTER_ABI'))
AVALANCHE_RPC = os.getenv('AVALANCHE_RPC')

# Connect to Avalanche
web3 = Web3(Web3.HTTPProvider(AVALANCHE_RPC))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

# Initialize Router Contract
router_contract = web3.eth.contract(address=ROUTER_CONTRACT_ADDRESS, abi=ROUTER_ABI)

# Cache for token prices to reduce API calls
price_cache = {}
price_cache_ttl = 60  # Cache duration in seconds

def get_token_contract(token_address, token_abi):
    """Returns the Web3 contract object for a given token address and ABI."""
    return web3.eth.contract(address=token_address, abi=token_abi)

def get_token_price_in_usd(token_symbol):
    """Fetches the current price of a token in USD, with caching."""
    current_time = time.time()
    if token_symbol in price_cache and current_time - price_cache[token_symbol]['timestamp'] < price_cache_ttl:
        return price_cache[token_symbol]['price']
    
    try:
        response = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={token_symbol}&vs_currencies=usd")
        response.raise_for_status()
        data = response.json()
        price = Decimal(data[token_symbol]['usd'])
        price_cache[token_symbol] = {'price': price, 'timestamp': current_time}
        return price
    except requests.RequestException as e:
        logger.error(f"Error fetching {token_symbol} price: {e}")
        return None

async def check_balance(update: Update, context: CallbackContext) -> None:
    """Check the balance of the user's wallet."""
    if update.message.chat.type != 'private':
        await update.message.reply_text("C'mon, man, don't give away your secrets. Talk to me in dm!")
        return

    user_id = update.message.from_user.id
    user_wallet = get_user_wallet(user_id)  # Fetch wallet from SQLite

    if not user_wallet:
        await update.message.reply_text("You don't have a wallet yet. Use /getwallet to create one.")
        return

    user_wallet_address = user_wallet['address']

    try:
        # Fetch AVAX balance
        avax_balance = web3.eth.get_balance(user_wallet_address)
        avax_balance_eth = web3.from_wei(avax_balance, 'ether')
        avax_price_usd = get_token_price_in_usd('avalanche-2')  # Coingecko ID for AVAX
        avax_balance_usd = avax_balance_eth * avax_price_usd if avax_price_usd else Decimal('0.00')

        # Create balance message for AVAX
        balance_message = f"$AVAX: {avax_balance_eth:.4f} | ${avax_balance_usd:.2f}\n"

        # Dynamically fetch balance for supported tokens from the environment
        token_list = ['RPEPE', 'BALLN', 'NOCHILL']  # Add other tokens as needed
        for token in token_list:
            token_address = os.getenv(f'{token}_TOKEN_CONTRACT_ADDRESS')
            token_abi = json.loads(os.getenv(f'TOKEN_ABI_{token}'))
            token_coingecko_id = os.getenv(f'COINGECKO_ID_{token.lower()}')  # Coingecko ID for the token

            token_contract = get_token_contract(token_address, token_abi)
            token_balance = token_contract.functions.balanceOf(user_wallet_address).call()
            token_balance_tokens = Decimal(token_balance) / Decimal(10 ** 18)

            # Fetch token price in USD
            token_price_usd = get_token_price_in_usd(token_coingecko_id)
            token_balance_usd = token_balance_tokens * token_price_usd if token_price_usd else Decimal('0.00')

            # Add to balance message
            balance_message += f"${token}: {token_balance_tokens:.4f} | ${token_balance_usd:.2f}\n"

        # Send balance message
        await update.message.reply_text(balance_message)

    except Exception as e:
        logger.error(f'An error occurred while fetching the balance: {e}')
        await update.message.reply_text('An error occurred while fetching your balance. Please try again later.')