#!/usr/bin/env python3
"""
Quick Telegram diagnostics - run from Mac terminal:
  cd ~/trading-agent && python3 test_telegram.py
"""
import sys
sys.path.insert(0, ".")

import requests
from dotenv import load_dotenv
import os

load_dotenv(".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

print("=" * 50)
print("TELEGRAM DIAGNOSTICS")
print("=" * 50)
print(f"Token: {TOKEN[:20]}..." if TOKEN else "Token: EMPTY ❌")
print(f"Chat ID: {CHAT_ID}" if CHAT_ID else "Chat ID: EMPTY ❌")
print()

if not TOKEN or not CHAT_ID:
    print("❌ Credentials missing in .env - check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
    sys.exit(1)

base_url = f"https://api.telegram.org/bot{TOKEN}"

# Step 1: Validate bot token
print("Step 1: Checking bot token...")
try:
    resp = requests.get(f"{base_url}/getMe", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        bot = data.get("result", {})
        print(f"  ✅ Bot valid: @{bot.get('username')} (id={bot.get('id')})")
    else:
        print(f"  ❌ Invalid token! HTTP {resp.status_code}: {resp.text[:200]}")
        sys.exit(1)
except Exception as e:
    print(f"  ❌ Network error: {e}")
    sys.exit(1)

# Step 2: Check if chat exists / bot can message it
print(f"\nStep 2: Sending test message to chat {CHAT_ID}...")
try:
    resp = requests.post(
        f"{base_url}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": "🤖 <b>Trading Agent</b> - Telegram test. If you see this, notifications are working! ✅",
            "parse_mode": "HTML",
        },
        timeout=10,
    )
    if resp.status_code == 200:
        print(f"  ✅ Message sent! Check your Telegram now.")
    else:
        data = resp.json()
        print(f"  ❌ Failed! HTTP {resp.status_code}")
        print(f"     Error: {data.get('description', resp.text[:200])}")
        if "chat not found" in resp.text.lower() or resp.status_code == 400:
            print()
            print("  💡 FIX: The bot can't find this chat.")
            print("     1. Open Telegram and search for your bot")
            print("     2. Send /start to the bot")
            print("     3. Then run this script again")
        elif resp.status_code == 403:
            print()
            print("  💡 FIX: You blocked the bot or it was removed from the chat.")
            print("     1. Open Telegram and find the bot")
            print("     2. Unblock it or send /start")
except Exception as e:
    print(f"  ❌ Network error: {e}")
    sys.exit(1)

print()
print("=" * 50)
print("Done! If message was received, Telegram is working.")
print("If not, restart the agent to apply the new logging")
print("and check logs/agent_*.log for 'Telegram:' entries.")
