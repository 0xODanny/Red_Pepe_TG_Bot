import logging
import os
from telegram import Update
from telegram.ext import CallbackContext
from web3 import Web3
from utils_token import get_active_users, get_user_wallet, clean_old_data, update_leaderboard

# Load environment variables
AVALANCHE_RPC = os.getenv('AVALANCHE_RPC')

# Initialize Web3 instance
web3 = Web3(Web3.HTTPProvider(AVALANCHE_RPC))

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Function to dynamically select the token contract and ABI
def get_token_contract(token_name):
    """Returns the appropriate token contract based on the token name."""
    token_contract_address = os.getenv(f'{token_name.upper()}_TOKEN_CONTRACT_ADDRESS')
    token_abi = json.loads(os.getenv(f'TOKEN_ABI_{token_name.upper()}', '[]'))

    if token_contract_address and token_abi:
        return web3.eth.contract(address=Web3.to_checksum_address(token_contract_address), abi=token_abi)
    else:
        raise ValueError(f"Unsupported or unknown token: {token_name}")

async def rain_command(update: Update, context: CallbackContext):
    """Handles the /rain command to distribute tokens among active users."""
    try:
        # Clean up old data in the database before processing
        clean_old_data()

        # Parse command arguments
        args = context.args
        if len(args) < 3:
            await update.message.reply_text("Usage: /rain <amount> <token> <hours>")
            return
        
        total_amount = float(args[0])  # Total amount to rain
        token = args[1].lower()  # Token to rain
        hours = int(args[2])     # Time window for user activity

        # Validate hours (between 1 and 24)
        if hours < 1 or hours > 24:
            await update.message.reply_text("Please specify a valid number of hours between 1 and 24.")
            return
        
        chat_id = update.message.chat_id
        initiator_id = update.message.from_user.id
        initiator_username = update.message.from_user.username

        # Get active users from the last X hours, excluding bots and users without wallets, in this chat only
        active_users = get_active_users(chat_id, hours)

        # Filter users that have a registered wallet and are not bots
        valid_active_users = [(user_id, username) for user_id, username in active_users 
                              if user_id and username and get_user_wallet(user_id) and str(user_id) != str(initiator_id)]
        
        # Check if there are any users to send the tokens to after filtering
        if not valid_active_users:
            await update.message.reply_text("No users with wallets were active to receive tokens. :(")
            return

        logger.info(f"Active users with wallets in the last {hours} hours (excluding initiator): {valid_active_users}")

        # Retrieve initiator wallet from database
        initiator_wallet = get_user_wallet(initiator_id)
        if not initiator_wallet:
            await update.message.reply_text("You don't have a registered wallet to send the tokens.")
            return

        # Get the token contract
        token_contract = get_token_contract(token)

        # Fetch token decimals
        token_decimals = token_contract.functions.decimals().call()

        # Convert total_amount and tokens_per_user to smallest units (token's decimals)
        total_amount_in_wei = int(total_amount * (10 ** token_decimals))  # Convert to smallest unit
        tokens_per_user_in_wei = total_amount_in_wei // len(valid_active_users)  # Split the total tokens equally

        # Estimate gas fee using a sample transfer
        try:
            sample_recipient_wallet = Web3.to_checksum_address(get_user_wallet(valid_active_users[0][0])['address'])

            # Build a dummy transaction to estimate gas
            gas_estimate = token_contract.functions.transfer(
                sample_recipient_wallet,
                tokens_per_user_in_wei
            ).estimate_gas({
                'from': Web3.to_checksum_address(initiator_wallet['address'])
            })
        except Exception as e:
            logger.error(f"Error estimating gas: {e}. Using fallback gas limit.")
            gas_estimate = 21000  # Fallback gas limit for simple token transfer

        # Get the current gas price or fallback to a predefined value
        try:
            gas_price = web3.eth.gas_price
        except Exception as e:
            logger.error(f"Error fetching gas price: {e}. Using fallback gas price.")
            gas_price = web3.to_wei(30, 'gwei')  # Fallback gas price

        # Check if the initiator has sufficient token balance before proceeding
        initiator_balance = token_contract.functions.balanceOf(initiator_wallet['address']).call()
        total_transfer_amount = tokens_per_user_in_wei * len(valid_active_users)

        if initiator_balance < total_transfer_amount:
            await update.message.reply_text("Insufficient token balance to complete the transaction.")
            return

        # Check if the initiator has sufficient AVAX balance to cover gas fees
        total_gas_fee = gas_estimate * gas_price * len(valid_active_users)  # Account for multiple transfers
        avax_balance = web3.eth.get_balance(Web3.to_checksum_address(initiator_wallet['address']))

        if avax_balance < total_gas_fee:
            await update.message.reply_text("Insufficient AVAX balance to cover gas fees.")
            return

        logger.debug(f"Gas estimate: {gas_estimate}, Gas price: {gas_price}, Total gas fee: {total_gas_fee}")

        # Perform token transfers
        nonce = web3.eth.get_transaction_count(Web3.to_checksum_address(initiator_wallet['address']))
        tx_hashes = []

        for user_id, username in valid_active_users:
            recipient_wallet = get_user_wallet(user_id)
            if recipient_wallet:
                try:
                    gas_estimate = token_contract.functions.transfer(
                        Web3.to_checksum_address(recipient_wallet['address']),
                        tokens_per_user_in_wei
                    ).estimate_gas({
                        'from': Web3.to_checksum_address(initiator_wallet['address'])
                    })
                except Exception as e:
                    logger.error(f"Error estimating gas for {username} (Wallet: {recipient_wallet['address']}): {e}. Using fallback gas limit.")
                    gas_estimate = 21000  # Fallback gas limit for simple token transfer

                # Create the token transfer transaction
                tx = token_contract.functions.transfer(
                    Web3.to_checksum_address(recipient_wallet['address']),
                    tokens_per_user_in_wei
                ).build_transaction({
                    'from': Web3.to_checksum_address(initiator_wallet['address']),
                    'gas': gas_estimate,
                    'gasPrice': gas_price,
                    'nonce': nonce
                })

                # Sign the transaction
                try:
                    signed_tx = web3.eth.account.sign_transaction(tx, private_key=initiator_wallet['private_key'])
                except Exception as e:
                    logger.error(f"Failed to sign the transaction for {username} (Wallet: {recipient_wallet['address']}). Error: {e}")
                    continue

                raw_tx = signed_tx.rawTransaction

                # Send the signed transaction
                try:
                    tx_hash = web3.eth.send_raw_transaction(raw_tx)
                    tx_hashes.append(tx_hash)
                    logger.info(f"Sent {tokens_per_user_in_wei} to {username} (Wallet: {recipient_wallet['address']}). Transaction Hash: {tx_hash.hex()}")
                except Exception as e:
                    logger.error(f"Failed to send transaction to {username} (Wallet: {recipient_wallet['address']}). Error: {e}")
                    continue

                # Increment the nonce for the next transaction
                nonce += 1

        # Check if any transactions were made
        if tx_hashes:
            tx_hash_str = ', '.join([tx_hash.hex() for tx_hash in tx_hashes])
            logger.info(f"Transaction hash(es): {tx_hash_str}")
        else:
            logger.error("Failed to execute rain transaction.")

        # Construct the Snowtrace link for the transaction
        tx_hash_str = tx_hashes[0].hex() if tx_hashes else "N/A"

        # List of users who received the tokens
        recipient_usernames = [username for user_id, username in valid_active_users]

        logger.info(f"Users with valid wallets: {recipient_usernames}")

        if not recipient_usernames:
            await update.message.reply_text(f"No users with valid wallets to receive the tokens.")
            return

        # Update the leaderboard for the initiator
        update_leaderboard(
            user_id=initiator_id,
            username=initiator_username,
            amount=total_amount,
            action='tips',
            token=token
        )

        # Display the message with the recipients and the clickable "snowtrace link"
        recipients = "\n".join([f"{i+1}. @{username}" for i, username in enumerate(recipient_usernames)])
        message = (
            f"The following users split the {total_amount} {token} who were active in the last {hours} hours in this chat:\n"
            f"{recipients}\n\n"
            f"<a href='https://snowtrace.io/tx/0x{tx_hash_str}'>snowtrace link</a>"
        )

        # Send the message with HTML parsing enabled so that "snowtrace link" is clickable
        await update.message.reply_text(message, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error in /rain command: {e}")
        await update.message.reply_text("An error occurred while executing the rain command.")