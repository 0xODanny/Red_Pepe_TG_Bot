import json
import sqlite3
import os

# Path to the SQLite database and JSON file
WALLETS_DB_PATH = 'wallets.db'
WALLETS_JSON_PATH = 'wallets.json'

# Initialize SQLite Wallets Database
def init_wallets_db():
    conn = sqlite3.connect(WALLETS_DB_PATH)
    c = conn.cursor()
    # Create the wallets table
    c.execute('''
        CREATE TABLE IF NOT EXISTS wallets (
            user_id TEXT PRIMARY KEY,      -- Unique Telegram user ID
            address TEXT NOT NULL,         -- Public wallet address
            private_key TEXT NOT NULL      -- Private key of the wallet
        )
    ''')
    conn.commit()
    conn.close()

# Migrate data from wallets.json to wallets.db
def migrate_wallets_json_to_db():
    if os.path.exists(WALLETS_JSON_PATH):
        with open(WALLETS_JSON_PATH, 'r') as f:
            wallets = json.load(f)
        
        # Insert wallets into SQLite database
        conn = sqlite3.connect(WALLETS_DB_PATH)
        c = conn.cursor()
        for user_id, wallet_data in wallets.items():
            c.execute('''
                INSERT OR REPLACE INTO wallets (user_id, address, private_key)
                VALUES (?, ?, ?)
            ''', (user_id, wallet_data['address'], wallet_data['private_key']))
        conn.commit()
        conn.close()

        print("Wallets migrated from JSON to SQLite successfully.")
    else:
        print(f"File {WALLETS_JSON_PATH} not found.")

# Call the functions to create the database and migrate the data
init_wallets_db()
migrate_wallets_json_to_db()