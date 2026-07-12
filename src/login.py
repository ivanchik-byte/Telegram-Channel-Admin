import os
from telethon.sync import TelegramClient
from dotenv import load_dotenv

# Bypass validation for login
load_dotenv()

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")

if not API_ID or not API_HASH:
    print("API_ID and API_HASH must be set in .env")
    exit(1)

# Save session in data/ folder
SESSION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'anon')

def main():
    print(f"Creating session at: {SESSION_FILE}.session")
    with TelegramClient(SESSION_FILE, API_ID, API_HASH) as client:
        print("Logged in successfully! The session file has been created.")

if __name__ == "__main__":
    main()
