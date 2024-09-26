import logging
from decimal import Decimal
from telegram import Update
from telegram.ext import CallbackContext
from web3 import Web3
from web3.middleware import geth_poa_middleware
from dotenv import load_dotenv
import os
import json
import requests  # To fetch AVAX price in USD

# Load environment variables
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

router_contract = web3.eth.contract(address=ROUTER_CONTRACT_ADDRESS, abi=ROUTER_ABI)

# Mapping for token addresses
token_addresses = {
    'avax': '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7'  # AVAX Address
}

# Function to fetch AVAX/USD price from CoinGecko
def get_avax_price_in_usd() -> Decimal:
    try:
        response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=avalanche-2&vs_currencies=usd')
        response_data = response.json()
        avax_price = Decimal(response_data['avalanche-2']['usd'])
        return avax_price
    except Exception as e:
        logger.error(f"Error fetching AVAX price in USD: {e}")
        return Decimal(0)

# Function to fetch AVAX/token conversion rates
def get_avax_to_token_rate(token: str, amount_in_avax: Decimal) -> Decimal:
    """
    Convert AVAX to the specified token using the DEX router.
    """
    try:
        token_address = token_addresses.get(token)
        if token_address is None:
            raise ValueError(f"Unsupported token: {token}")

        amount_in_wei = web3.to_wei(amount_in_avax, 'ether')
        amounts_out = router_contract.functions.getAmountsOut(
            amount_in_wei,
            [token_addresses['avax'], token_address]
        ).call()

        return Decimal(amounts_out[1]) / Decimal(10 ** 18)  # Convert wei to the token's base unit
    except Exception as e:
        logger.error(f"Error fetching AVAX to {token} rate: {e}")
        return Decimal(0)

# Function to fetch token/AVAX conversion rates
def get_token_to_avax_rate(token: str, amount_in_token: Decimal) -> Decimal:
    """
    Convert the specified token to AVAX using the DEX router.
    """
    try:
        token_address = token_addresses.get(token)
        if token_address is None:
            raise ValueError(f"Unsupported token: {token}")

        amount_in_wei = web3.to_wei(amount_in_token, 'ether')
        amounts_out = router_contract.functions.getAmountsOut(
            amount_in_wei,
            [token_address, token_addresses['avax']]
        ).call()

        return Decimal(amounts_out[1]) / Decimal(10 ** 18)  # Convert wei to AVAX
    except Exception as e:
        logger.error(f"Error fetching {token} to AVAX rate: {e}")
        return Decimal(0)

# Conversion handler for AVAX/token, token/AVAX, USD/AVAX, and Token/USD
async def convert(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 3:
        await update.message.reply_text('Usage: /convert <amount> <from_token> <to_token>')
        return

    try:
        amount = Decimal(context.args[0])
        from_token = context.args[1].lower()
        to_token = context.args[2].lower()

        # Validate tokens
        supported_tokens = list(token_addresses.keys()) + ['usd']
        if from_token not in supported_tokens or to_token not in supported_tokens:
            await update.message.reply_text(f'Supported tokens are: {", ".join(supported_tokens)}.')
            return

        # Handle AVAX to token conversion
        if from_token == 'avax' and to_token != 'usd':
            converted_amount = get_avax_to_token_rate(to_token, amount)
            await update.message.reply_text(f'Conversion result: {amount} AVAX is approximately {converted_amount:.4f} {to_token.upper()}.')

        # Handle token to AVAX conversion
        elif to_token == 'avax' and from_token != 'usd':
            converted_amount = get_token_to_avax_rate(from_token, amount)
            await update.message.reply_text(f'Conversion result: {amount} {from_token.upper()} is approximately {converted_amount:.4f} AVAX.')

        # Handle AVAX to USD conversion
        elif from_token == 'avax' and to_token == 'usd':
            avax_price = get_avax_price_in_usd()
            if avax_price > 0:
                converted_amount = amount * avax_price
                await update.message.reply_text(f'Conversion result: {amount} AVAX is approximately ${converted_amount:.4f} USD.')
            else:
                await update.message.reply_text('Failed to fetch AVAX to USD conversion rate.')

        # Handle USD to AVAX conversion
        elif from_token == 'usd' and to_token == 'avax':
            avax_price = get_avax_price_in_usd()
            if avax_price > 0:
                converted_amount = amount / avax_price
                await update.message.reply_text(f'Conversion result: ${amount} USD is approximately {converted_amount:.4f} AVAX.')
            else:
                await update.message.reply_text('Failed to fetch AVAX to USD conversion rate.')

        # Handle Token to USD conversion
        elif from_token != 'usd' and to_token == 'usd':
            avax_price = get_avax_price_in_usd()
            if avax_price > 0:
                avax_amount = get_token_to_avax_rate(from_token, amount)
                converted_amount = avax_amount * avax_price
                await update.message.reply_text(f'Conversion result: {amount} {from_token.upper()} is approximately ${converted_amount:.4f} USD.')
            else:
                await update.message.reply_text('Failed to fetch AVAX to USD conversion rate.')

        # Handle USD to Token conversion
        elif from_token == 'usd' and to_token != 'avax':
            avax_price = get_avax_price_in_usd()
            if avax_price > 0:
                avax_amount = amount / avax_price
                converted_amount = get_avax_to_token_rate(to_token, avax_amount)
                await update.message.reply_text(f'Conversion result: ${amount} USD is approximately {converted_amount:.4f} {to_token.upper()}.')
            else:
                await update.message.reply_text('Failed to fetch AVAX to USD conversion rate.')

        else:
            await update.message.reply_text('Invalid conversion. Only AVAX to token, token to AVAX, AVAX to USD, USD to AVAX, token to USD, and USD to token conversions are supported.')

    except Exception as e:
        logger.error(f"An error occurred during conversion: {e}")
        await update.message.reply_text('An error occurred while trying to execute the conversion.')