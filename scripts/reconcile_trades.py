#!/usr/bin/env python3
"""
Reconcile trades from Alpaca API → SQLite DB.

Run this script manually to sync any missing trades from Alpaca into the DB.
Useful for recovering from the save_trade() bug that caused trades to be
lost before 2026-03-26.

Usage:
    python scripts/reconcile_trades.py                  # Last 7 days
    python scripts/reconcile_trades.py --days 30        # Last 30 days
    python scripts/reconcile_trades.py --date 2026-03-23  # Specific date
"""

import os
import sys
import sqlite3
import argparse
from datetime import datetime, timedelta, date
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

import requests

DB_PATH = PROJECT_ROOT / 'memory' / 'trading.db'
ALPACA_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET_KEY')
ALPACA_BASE = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

headers = {
    'APCA-API-KEY-ID': ALPACA_KEY,
    'APCA-API-SECRET-KEY': ALPACA_SECRET,
}


def get_alpaca_orders(start_date: date, end_date: date) -> list:
    """Fetch all orders from Alpaca for a date range."""
    after_dt = f"{start_date.isoformat()}T00:00:00Z"
    until_dt = f"{(end_date + timedelta(days=1)).isoformat()}T00:00:00Z"

    r = requests.get(
        f"{ALPACA_BASE}/v2/orders",
        headers=headers,
        params={
            'status': 'all',
            'after': after_dt,
            'until': until_dt,
            'limit': 500,
            'direction': 'asc',
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def reconcile(target_date: date = None, days: int = 7):
    """Reconcile missing trades."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")

    if target_date:
        start = target_date
        end = target_date
    else:
        end = date.today()
        start = end - timedelta(days=days)

    print(f"🔍 Reconciling trades from {start} to {end}...")

    # Get existing order IDs from DB
    db_order_ids = set()
    rows = conn.execute(
        "SELECT alpaca_order_id FROM trades WHERE alpaca_order_id IS NOT NULL"
    ).fetchall()
    for r in rows:
        db_order_ids.add(r['alpaca_order_id'])
    print(f"📊 DB has {len(db_order_ids)} known order IDs")

    # Fetch from Alpaca
    orders = get_alpaca_orders(start, end)
    filled = [o for o in orders if o['status'] in ('filled', 'partially_filled')]
    print(f"📊 Alpaca has {len(filled)} filled orders in range")

    # Find missing
    missing = 0
    for order in filled:
        if order['id'] in db_order_ids:
            continue

        avg_price = float(order.get('filled_avg_price', 0))
        filled_qty = float(order.get('filled_qty', 0))
        if avg_price == 0 or filled_qty == 0:
            continue

        entry_time = order['created_at'][:19]
        client_id = order.get('client_order_id', '')
        strategy = client_id.split('_')[0] if client_id else 'unknown_alpaca'

        trade_data = {
            'timestamp': entry_time,
            'strategy': strategy,
            'symbol': order['symbol'],
            'side': order['side'],
            'entry_price': avg_price,
            'quantity': filled_qty,
            'status': 'open',
            'alpaca_order_id': order['id'],
            'notes': f'Reconciled by script on {datetime.now().isoformat()}',
        }

        try:
            fields = list(trade_data.keys())
            placeholders = ', '.join(['?'] * len(fields))
            columns = ', '.join(fields)
            values = [trade_data[f] for f in fields]
            conn.execute(f"INSERT INTO trades ({columns}) VALUES ({placeholders})", values)
            missing += 1
            print(f"  ✅ {order['side']:5} {order['symbol']:6} @ ${avg_price:.2f} "
                  f"qty={filled_qty} ({entry_time})")
        except Exception as e:
            print(f"  ❌ Failed: {e}")

    if missing > 0:
        conn.commit()
        print(f"\n🔄 Reconciled {missing} missing trades")
    else:
        print(f"\n✅ All trades already in sync")

    conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reconcile Alpaca trades to DB')
    parser.add_argument('--days', type=int, default=7, help='Look back N days')
    parser.add_argument('--date', type=str, help='Specific date (YYYY-MM-DD)')
    args = parser.parse_args()

    if args.date:
        target = date.fromisoformat(args.date)
        reconcile(target_date=target)
    else:
        reconcile(days=args.days)
