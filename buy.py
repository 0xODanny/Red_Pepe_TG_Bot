import logging
from decimal import Decimal
from telegram import Update
from telegram.ext import CallbackContext
from web3 import Web3
from web3.middleware import geth_poa_middleware
from dotenv import load_dotenv
import os
import json
from utils_token import get_user_wallet, update_leaderboard, fetch_token_price_in_avax, format_amount, get_token_contract

# Load environment variables from .env
load_dotenv()

# Get environment variables
RPC_URL = os.getenv('AVALANCHE_RPC')
ROUTER_CONTRACT_ADDRESS = os.getenv('ROUTER_CONTRACT_ADDRESS')
MAIN_WALLET_ADDRESS = os.getenv('MAIN_WALLET_ADDRESS')

# Define constants for token operations and fees
LOW_FEE_RATE = Decimal('0.0005')  # 0.05% fee
HIGH_FEE_RATE = Decimal('0.006942')  # 0.6942% fee
SLIPPAGE_TOLERANCE = Decimal('0.05')  # 5% slippage tolerance

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connect to the blockchain
web3 = Web3(Web3.HTTPProvider(RPC_URL))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

# Initialize the router contract
router_contract = web3.eth.contract(address=ROUTER_CONTRACT_ADDRESS, abi=json.loads(os.getenv('ROUTER_ABI', '[]')))

async def buy(update: Update, context: CallbackContext) -> None:
    """Handles the /buy command to purchase tokens using AVAX."""
    
    # Ensure the correct usage of the command
    if len(context.args) != 2:
        await update.message.reply_text('Usage: /buy <amount> <token>')
        return

    try:
        amount = Decimal(context.args[0])  # Parse the amount
        token = context.args[1].lower()    # Parse the token name
    except Exception:
        await update.message.reply_text('Invalid amount format. Please enter a numeric value for the amount.')
        return

    try:
        # Get the token contract and ABI
        token_contract_address, token_abi = get_token_contract(token)
    except ValueError as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(str(e))
        return

    try:
        # Get user's wallet from the database
        user_id = str(update.message.from_user.id)
        user_wallet = get_user_wallet(user_id)

        if not user_wallet:
            await update.message.reply_text("You don't have a wallet yet. Use /getwallet to create one.")
            return

        user_wallet_address = user_wallet['address']
        user_private_key = user_wallet['private_key']

        # Check user's token balance for determining the fee
        rpepe_contract = web3.eth.contract(address=os.getenv('RPEPE_TOKEN_CONTRACT_ADDRESS'), abi=json.loads(os.getenv('TOKEN_ABI_RPEPE', '[]')))
        rpepe_balance = Decimal(rpepe_contract.functions.balanceOf(user_wallet_address).call())

        # Determine the fee rate
        fee_rate = LOW_FEE_RATE if rpepe_balance >= Decimal(os.getenv('MINIMUM_RPEPE_BALANCE', '4206900000')) else HIGH_FEE_RATE

        # Get AVAX balance of the user
        avax_balance_wei = web3.eth.get_balance(user_wallet_address)
        avax_balance = Decimal(web3.from_wei(avax_balance_wei, 'ether'))

        # Fetch token price in AVAX and calculate amount needed
        token_price_in_avax = fetch_token_price_in_avax(token_contract_address)
        amount_in_avax = amount * token_price_in_avax

        # Calculate the fee and the total AVAX needed
        fee_amount = amount_in_avax * fee_rate
        total_amount_needed = amount_in_avax + fee_amount

        # Estimate gas cost
        current_gas_price = web3.eth.gas_price
        gas_estimate = router_contract.functions.swapExactAVAXForTokens(
            int(Web3.to_wei(amount * (1 - SLIPPAGE_TOLERANCE), 'ether')),
            [web3.to_checksum_address('0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7'), token_contract_address],
            web3.to_checksum_address(user_wallet_address),
            int((web3.eth.get_block('latest')['timestamp']) + 10 * 60)
        ).estimate_gas({'from': user_wallet_address, 'value': Web3.to_wei(amount_in_avax, 'ether')})

        gas_cost = Decimal(web3.from_wei(gas_estimate * current_gas_price, 'ether'))

        # Calculate total cost including gas
        final_total_amount_needed = total_amount_needed + gas_cost

        if avax_balance < final_total_amount_needed:
            await update.message.reply_text("Insufficient AVAX balance for transaction, including gas fees.")
            return

        # Build transaction to buy the token
        transaction = router_contract.functions.swapExactAVAXForTokens(
            int(Web3.to_wei(amount * (1 - SLIPPAGE_TOLERANCE), 'ether')),
            [web3.to_checksum_address('0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7'), token_contract_address],
            web3.to_checksum_address(user_wallet_address),
            int((web3.eth.get_block('latest')['timestamp']) + 10 * 60)
        ).build_transaction({
            'from': web3.to_checksum_address(user_wallet_address),
            'value': Web3.to_wei(amount_in_avax, 'ether'),
            'gas': gas_estimate,
            'gasPrice': current_gas_price,
            'nonce': web3.eth.get_transaction_count(user_wallet_address),
            'chainId': 43114
        })

        # Sign and send the transaction
        signed_txn = web3.eth.account.sign_transaction(transaction, private_key=user_private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)

        # Log and notify the user
        formatted_amount = format_amount(amount, token)
        formatted_amount_avax = format_amount(amount_in_avax, 'avax')
        logger.info(f"User {update.message.from_user.username or user_id} bought {formatted_amount} {token.upper()} for {formatted_amount_avax} AVAX with fee {fee_amount} AVAX")
        await update.message.reply_text(
            f'Transaction sent! You purchased {formatted_amount} {token.upper()} for {formatted_amount_avax} AVAX. [View on Snowtrace](https://snowtrace.io/tx/0x{tx_hash.hex()})',
            parse_mode='Markdown'
        )

        # Update the leaderboard
        username = update.message.from_user.username or f"User {user_id}"
        update_leaderboard(user_id, username, amount, 'buys', token)

    except Exception as e:
        logger.error(f'An error occurred while trying to buy {token.upper()}: {e}')
        await update.message.reply_text(f'An error occurred while trying to buy {token.upper()}. Please try again later.')