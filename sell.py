import logging
from decimal import Decimal, InvalidOperation
from telegram import Update
from telegram.ext import CallbackContext
from web3 import Web3
from web3.middleware import geth_poa_middleware
from dotenv import load_dotenv
import os
import json
from utils_token import get_user_wallet, get_token_contract

# Load environment variables from .env
load_dotenv()

# Get environment variables
RPC_URL = os.getenv('AVALANCHE_RPC')
ROUTER_CONTRACT_ADDRESS = os.getenv('ROUTER_CONTRACT_ADDRESS')

# Load ABI for the router contract
ROUTER_ABI = json.loads(os.getenv('ROUTER_ABI', '[]'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connect to Avalanche
web3 = Web3(Web3.HTTPProvider(RPC_URL))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

# Initialize the Trader Joe router contract
router_contract = web3.eth.contract(address=ROUTER_CONTRACT_ADDRESS, abi=ROUTER_ABI)

# Define constants
SLIPPAGE_TOLERANCE = Decimal('0.05')  # 5% slippage tolerance
MAX_WAIT_TIME = 180  # Maximum wait time for transaction receipt (in seconds)

async def sell(update: Update, context: CallbackContext) -> None:
    """Handles the /sell command to sell tokens for AVAX."""
    
    # Ensure the command is used in a private chat
    if update.message.chat.type != 'private':
        await update.message.reply_text("Let's do this in a private chat.")
        return

    # Ensure correct usage of the command
    if len(context.args) != 2:
        await update.message.reply_text('Usage: /sell <amount> <token>')
        return

    try:
        # Parse the amount and token
        amount = Decimal(context.args[0].strip())  # Convert the first argument to Decimal
        token = context.args[1].lower().strip()    # Convert the second argument to lowercase
    except InvalidOperation:
        await update.message.reply_text("Invalid amount. Please provide a numeric value.")
        return

    try:
        # Load user wallet from the database
        user_id = str(update.message.from_user.id)
        user_wallet = get_user_wallet(user_id)

        if not user_wallet:
            await update.message.reply_text("You don't have a wallet yet. Use /getwallet to create one.")
            return

        user_wallet_address = user_wallet['address']
        user_private_key = user_wallet['private_key']

        # Execute the logic to sell the token
        await sell_token_logic(token, amount, user_wallet_address, user_private_key, update)

    except Exception as e:
        logger.error(f'An error occurred while trying to sell {token.upper()}: {e}')
        await update.message.reply_text(f'An error occurred while trying to sell {token.upper()}: {e}')

async def sell_token_logic(token, amount, user_wallet_address, user_private_key, update):
    """Logic for selling any token using the Trader Joe router."""
    try:
        # Get the token contract details
        token_contract_address, token_abi = get_token_contract(token)
        token_contract = web3.eth.contract(address=token_contract_address, abi=token_abi)
        amount_in_wei = web3.to_wei(amount, 'ether')

        # Check if user has enough tokens
        token_balance = token_contract.functions.balanceOf(user_wallet_address).call()
        logger.info(f"User token balance for {token.upper()}: {token_balance}")
        if token_balance < amount_in_wei:
            await update.message.reply_text(f"Insufficient {token.upper()} token balance.")
            return

        # Handle token allowance
        await handle_allowance(token_contract, user_wallet_address, user_private_key, amount_in_wei, ROUTER_CONTRACT_ADDRESS)

        # Proceed with swap transaction using the Trader Joe router
        await execute_swap(router_contract, token_contract, user_wallet_address, user_private_key, amount_in_wei, update)

    except Exception as e:
        logger.error(f'An error occurred while trying to sell {token.upper()}: {e}')
        await update.message.reply_text(f'An error occurred while trying to sell {token.upper()}: {e}')

async def handle_allowance(token_contract, user_wallet_address, user_private_key, amount_in_wei, router_address):
    """Handles the allowance check and approval process for the token."""
    current_allowance = token_contract.functions.allowance(user_wallet_address, router_address).call()
    logger.info(f"Current allowance: {current_allowance}")

    # Fetch the latest nonce for transaction signing
    nonce = web3.eth.get_transaction_count(user_wallet_address)

    if current_allowance < amount_in_wei:
        try:
            max_uint256 = 2**256 - 1  # Approving the maximum allowable amount
            current_gas_price = web3.eth.gas_price
            gas_estimate = int(token_contract.functions.approve(
                router_address, max_uint256
            ).estimate_gas({'from': user_wallet_address}) * 1.2)

            approve_txn = token_contract.functions.approve(
                router_address, max_uint256
            ).build_transaction({
                'from': user_wallet_address,
                'gas': gas_estimate,
                'gasPrice': int(current_gas_price * 1.2),
                'nonce': nonce,
                'chainId': 43114
            })

            signed_approve_txn = web3.eth.account.sign_transaction(approve_txn, private_key=user_private_key)
            raw_approve_txn = signed_approve_txn.rawTransaction
            tx_hash = web3.eth.send_raw_transaction(raw_approve_txn)

            logger.info(f"Approval transaction sent: {tx_hash.hex()}")
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=MAX_WAIT_TIME)

            if receipt.status != 1:
                raise Exception("Approval transaction failed or was reverted.")
            logger.info("Allowance approved successfully.")
        except Exception as e:
            raise Exception(f"Approval failed: {e}")

    else:
        logger.info("Allowance already sufficient.")

async def execute_swap(router_contract, token_contract, user_wallet_address, user_private_key, amount_in_wei, update):
    """Executes the swap transaction to sell tokens for AVAX."""
    try:
        # Get the current exchange rate for the token to AVAX
        amounts_out = router_contract.functions.getAmountsOut(
            amount_in_wei,
            [token_contract.address, web3.to_checksum_address('0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7')]
        ).call()

        min_avax_out = int(amounts_out[1] * (1 - SLIPPAGE_TOLERANCE))
        logger.info(f"Calculated minimum AVAX out: {min_avax_out}")

        # Estimate gas required for swap
        current_gas_price = web3.eth.gas_price
        gas_estimate = int(router_contract.functions.swapExactTokensForAVAX(
            amount_in_wei,
            min_avax_out,
            [token_contract.address, web3.to_checksum_address('0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7')],
            web3.to_checksum_address(user_wallet_address),
            int((web3.eth.get_block('latest')['timestamp']) + 10 * 60)
        ).estimate_gas({'from': user_wallet_address}) * 1.2)

        # Prepare and sign the transaction
        transaction = router_contract.functions.swapExactTokensForAVAX(
            amount_in_wei,
            min_avax_out,
            [token_contract.address, web3.to_checksum_address('0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7')],
            web3.to_checksum_address(user_wallet_address),
            int((web3.eth.get_block('latest')['timestamp']) + 10 * 60)
        ).build_transaction({
            'from': web3.to_checksum_address(user_wallet_address),
            'gas': gas_estimate,
            'gasPrice': int(current_gas_price * 1.2),
            'nonce': web3.eth.get_transaction_count(user_wallet_address),
            'chainId': 43114
        })

        signed_txn = web3.eth.account.sign_transaction(transaction, private_key=user_private_key)
        raw_txn = signed_txn.rawTransaction
        tx_hash = web3.eth.send_raw_transaction(raw_txn)

        # Wait for transaction receipt
        sell_receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=MAX_WAIT_TIME)

        if sell_receipt.status != 1:
            await update.message.reply_text("The sale transaction failed. Please try again.")
            return

        # Notify the user with the transaction link
        snowtrace_link = f"https://snowtrace.io/tx/0x{tx_hash.hex()}"
        logger.info(f"User sold tokens with tx hash: {tx_hash.hex()}")
        await update.message.reply_text(
            f"Your sale was successful! [View transaction]({snowtrace_link})",
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f'An error occurred during the swap: {e}')
        await update.message.reply_text(f'An error occurred during the swap: {e}')