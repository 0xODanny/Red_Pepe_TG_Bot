# Red Pepe Telegram Bot

## Overview

The **Red Pepe Telegram Bot** is a multifunctional bot designed for cryptocurrency transactions on the Avalanche network. Users can buy, sell, tip, and rain tokens, check their balances, and view a leaderboard of the top buyers and tippers.

## Features

- **Buy Tokens:** Allows users to purchase supported tokens.
- **Sell Tokens:** Facilitates the selling of supported tokens with dynamic transaction fees.
- **Tip Tokens:** Users can tip other users in supported tokens.
- **Rain Tokens:** Distribute tokens to active users in the chat.
- **Convert Tokens:** Users can convert values between supported tokens. 
- **Check Balances:** Displays the user's token balance.
- **Leaderboard:** Shows the top 10 buyers and tippers, along with their total activity.
- **Wallet Management:** Manages wallets for each user, storing their address and private keys securely.

## Folder Structure

```plaintext
red-pepe-bot/
│
├── .env                     # Environment variables file
├── README.md                # This README file
├── requirements.txt         # Required Python packages
├── main.py                  # Main bot script
├── buy.py                   # Handles buy transactions
├── sell.py                  # Handles sell transactions
├── tip.py                   # Handles tipping functionality
├── balance.py               # Checks user balance
├── convert_tokens.py        # Handles token conversion
├── rain.py                  # Handles token rain functionality
├── welcome.py               # Initial welcome/start commands
├── utils_token.py           # Helper functions for wallets and leaderboard
│
├── wallets.db             	 # Stores user wallet information
├── leaderboard.json         # Stores leaderboard data
└── .gitignore               # Files and directories to ignore in Git

## Installation

Prerequisites

	•	Python 3.8 or higher
	•	Pip (Python package manager)

Clone the Repository
$ git clone https://github.com/your-username/red-pepe-bot.git
$ cd red-pepe-bot

## Install Dependencies

Run the following command to install all required dependencies:
$ pip install -r requirements.txt

## Configure Environment Variables

Create a .env file in the root directory with the following content:

TELEGRAM_TOKEN=your_telegram_bot_token
AVALANCHE_RPC=https://api.avax.network/ext/bc/C/rpc
TOKEN1_TOKEN_CONTRACT_ADDRESS=your_rpepe_token_contract_address
TOKEN2_TOKEN_CONTRACT_ADDRESS=your_balln_token_contract_address
ROUTER_CONTRACT_ADDRESS=your_router_contract_address
ROUTER_ABI='[your_router_abi]'
TOKEN_ABI_RPEPE='[your_TOKEN1_token_abi]'
TOKEN_ABI_BALLN='[your_TOKEN2_token_abi]'
MAIN_WALLET_ADDRESS=your_main_wallet_address
MAIN_WALLET_PRIVATE_KEY=your_main_wallets_private_key

Replace the placeholders with your actual token addresses, ABI strings, RPC URLs, and wallet address.

## Usage

Run the Bot

To start the bot, run:
$ python main.py

## Commands

	•	/redpepebot: Start the bot and receive a welcome message.
	•	/getwallet: Create a new wallet or check the existing one (private chat only).
	•	/balance: Check your current token balance (private chat only).
	•	/buy <amount> <token>: Buy a specified amount of tokens.
	•	/sell <amount> <token>: Sell a specified amount of tokens (private chat only).
	•	/tip <amount> <token>: Tip another user in tokens (must reply to a user’s message).
	•	/convert <amount> <from_token> <to_token>: Convert one token to another.
	•	/rain <amount> <token> <hours>: Distribute tokens among active users in the chat.
	•	/top10token1: Display the top 10 buyers and tippers for Token 1.
	•	/top10token2: Display the top 10 buyers and tippers for Token 2.
	•	/cancel: Cancel the current operation.

## Wallet Management

The bot automatically checks if a user already has a wallet created. If a wallet exists, it uses that wallet for all transactions and balance checks.

## Leaderboard

The bot maintains a leaderboard of the top buyers and tippers. The leaderboard is stored in leaderboard.json and updates automatically after each transaction. Use /top10token1 or /top10token2 to see the top users for each token.

## Contribution

Contributions are welcome! Please fork the repository, make your changes, and submit a pull request.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.

## Disclaimer

This bot is for educational purposes only. Use at your own risk. The author is not responsible for any financial losses or damages resulting from the use of this bot.