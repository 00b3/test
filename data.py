"""
📊 WALLET TRACKER - Live Data Collection
=========================================
Tracks a target wallet's trades and collects all data.
"""

import requests
import time
from datetime import datetime
import json
import os
from threading import Thread
from http.server import HTTPServer, SimpleHTTPRequestHandler

API_KEY = "api"
WALLET = "Ar2Y6o1QmrRAskjii1cRfijeKugHH13ycxW5cd7rro1x"
BASE = "https://data.solanatracker.io"

CHECK_INTERVAL = 4  # seconds between checks

def api(route, params=None):
    headers = {"x-api-key": API_KEY}
    url = f"{BASE}{route}"
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json()

def get_wallet_trades():
    data = api(f"/wallet/{WALLET}/trades", params={"limit": 100})
    return data.get("trades", [])

def get_token_analysis(mint):
    """Get detailed token info at time of trade"""
    try:
        data = api(f"/tokens/{mint}")
        token = data.get("token", {})
        pools = data.get("pools", [])
        risk = data.get("risk", {})
        events = data.get("events", {})
        
        primary_pool = pools[0] if pools else {}
        
        price_changes = {
            "1m": events.get("1m", {}).get("priceChangePercentage", 0),
            "5m": events.get("5m", {}).get("priceChangePercentage", 0),
            "15m": events.get("15m", {}).get("priceChangePercentage", 0),
            "1h": events.get("1h", {}).get("priceChangePercentage", 0),
        }
        
        pool_txns = primary_pool.get("txns", {})
        
        analysis = {
            "name": token.get("name", "Unknown"),
            "symbol": token.get("symbol", "???"),
            "mint": mint,
            "decimals": token.get("decimals", 0),
            "age_seconds": int(time.time()) - token.get("creation", {}).get("created_time", 0),
            "creator": token.get("creation", {}).get("creator", ""),
            "created_tx": token.get("creation", {}).get("created_tx", ""),
            "market_cap": primary_pool.get("marketCap", {}).get("usd", 0),
            "liquidity": primary_pool.get("liquidity", {}).get("usd", 0),
            "price_usd": primary_pool.get("price", {}).get("usd", 0),
            "price_sol": primary_pool.get("price", {}).get("quote", 0),
            "token_supply": primary_pool.get("tokenSupply", 0),
            "holders": data.get("holders", 0),
            "total_txns": data.get("txns", 0),
            "buys": data.get("buys", 0),
            "sells": data.get("sells", 0),
            "buy_sell_ratio": data.get("buys", 0) / data.get("sells", 1) if data.get("sells", 0) > 0 else 0,
            "pool_buys": pool_txns.get("buys", 0),
            "pool_sells": pool_txns.get("sells", 0),
            "pool_total_txns": pool_txns.get("total", 0),
            "pool_volume": pool_txns.get("volume", 0),
            "pool_volume_24h": pool_txns.get("volume24h", 0),
            "price_change_1m": price_changes["1m"],
            "price_change_5m": price_changes["5m"],
            "price_change_15m": price_changes["15m"],
            "price_change_1h": price_changes["1h"],
            "lp_burned": primary_pool.get("lpBurn", 0),
            "freeze_authority": primary_pool.get("security", {}).get("freezeAuthority"),
            "mint_authority": primary_pool.get("security", {}).get("mintAuthority"),
            "top10_holders_pct": risk.get("top10", 0),
            "dev_holdings_pct": risk.get("dev", {}).get("percentage", 0),
            "dev_holdings_amount": risk.get("dev", {}).get("amount", 0),
            "risk_score": risk.get("score", 0),
            "is_rugged": risk.get("rugged", False),
            "jupiter_verified": risk.get("jupiterVerified", False),
            "sniper_count": risk.get("snipers", {}).get("count", 0),
            "sniper_balance_pct": risk.get("snipers", {}).get("totalPercentage", 0),
            "insider_count": risk.get("insiders", {}).get("count", 0),
            "insider_balance_pct": risk.get("insiders", {}).get("totalPercentage", 0),
            "market": primary_pool.get("market", "unknown"),
            "pool_id": primary_pool.get("poolId", ""),
            "quote_token": primary_pool.get("quoteToken", ""),
            "deployer": primary_pool.get("deployer", ""),
            "has_metadata": token.get("hasFileMetaData", False),
            "image_url": token.get("image", ""),
            "description": token.get("description", ""),
        }
        return analysis
    except Exception as e:
        print(f"      ⚠️  Failed to get token analysis: {e}")
        return None


class WalletTracker:
    def __init__(self):
        self.history = []
        self.seen_txs = set()
        self.start_time = datetime.now()
        self.positions = {}  # Track open positions for P/L calc
        
    def process_trade(self, t):
        tx_sig = t.get("tx", "")
        if tx_sig in self.seen_txs:
            return None
        
        self.seen_txs.add(tx_sig)
        
        from_data = t.get("from", {})
        to_data = t.get("to", {})
        
        from_token = from_data.get("token", {})
        to_token = to_data.get("token", {})
        
        from_address = from_data.get("address", "")
        to_address = to_data.get("address", "")
        
        from_symbol = from_token.get("symbol", "")
        to_symbol = to_token.get("symbol", "")
        
        ts = datetime.fromtimestamp(t.get("time", 0) / 1000)
        
        trade_result = None
        
        # BUY: SOL -> Token
        if from_symbol == "SOL" and to_symbol != "SOL":
            sol_spent = from_data.get("amount", 0)
            tokens_received = to_data.get("amount", 0)
            price_usd = to_data.get("priceUsd", 0)
            value_usd = t.get("volume", {}).get("usd", 0)
            
            token_analysis = get_token_analysis(to_address)
            
            # Track position for P/L calculation
            if to_address not in self.positions:
                self.positions[to_address] = {
                    "total_tokens": 0,
                    "total_sol_spent": 0,
                    "avg_price": 0,
                    "symbol": to_symbol,
                    "name": to_token.get("name", "Unknown")
                }
            
            pos = self.positions[to_address]
            pos["total_tokens"] += tokens_received
            pos["total_sol_spent"] += sol_spent
            pos["avg_price"] = (pos["total_sol_spent"] / pos["total_tokens"]) if pos["total_tokens"] > 0 else 0
            
            trade_result = {
                "timestamp": ts,
                "timestamp_detected": datetime.now(),
                "action": "BUY",
                "token": to_address,
                "token_name": to_token.get("name", "Unknown"),
                "token_symbol": to_symbol,
                "sol_amount": sol_spent,
                "token_amount": tokens_received,
                "price_usd": price_usd,
                "value_usd": value_usd,
                "tx": tx_sig,
                "analysis": token_analysis
            }
            self.history.append(trade_result)
                
        # SELL: Token -> SOL
        elif from_symbol != "SOL" and to_symbol == "SOL":
            tokens_sold = from_data.get("amount", 0)
            sol_received = to_data.get("amount", 0)
            price_usd = from_data.get("priceUsd", 0)
            value_usd = t.get("volume", {}).get("usd", 0)
            
            token_analysis = get_token_analysis(from_address)
            
            # Calculate P/L if we have position data
            pnl_sol = 0
            pnl_pct = 0
            if from_address in self.positions:
                pos = self.positions[from_address]
                if pos["total_tokens"] > 0:
                    # Calculate what portion of position is being sold
                    portion = min(tokens_sold / pos["total_tokens"], 1.0)
                    cost_basis_sol = pos["total_sol_spent"] * portion
                    pnl_sol = sol_received - cost_basis_sol
                    pnl_pct = (pnl_sol / cost_basis_sol * 100) if cost_basis_sol > 0 else 0
                    
                    # Update position
                    pos["total_tokens"] -= tokens_sold
                    pos["total_sol_spent"] -= cost_basis_sol
                    if pos["total_tokens"] <= 0:
                        pos["total_tokens"] = 0
                        pos["total_sol_spent"] = 0
            
            trade_result = {
                "timestamp": ts,
                "timestamp_detected": datetime.now(),
                "action": "SELL",
                "token": from_address,
                "token_name": from_token.get("name", "Unknown"),
                "token_symbol": from_symbol,
                "sol_amount": sol_received,
                "token_amount": tokens_sold,
                "price_usd": price_usd,
                "value_usd": value_usd,
                "pnl_sol": pnl_sol,
                "pnl_pct": pnl_pct,
                "tx": tx_sig,
                "analysis": token_analysis
            }
            self.history.append(trade_result)
        
        return trade_result
    
    def get_stats(self):
        """Calculate trading stats"""
        buys = [t for t in self.history if t["action"] == "BUY"]
        sells = [t for t in self.history if t["action"] == "SELL"]
        
        total_sol_spent = sum(t["sol_amount"] for t in buys)
        total_sol_received = sum(t["sol_amount"] for t in sells)
        
        wins = len([t for t in sells if t.get("pnl_sol", 0) > 0])
        losses = len([t for t in sells if t.get("pnl_sol", 0) < 0])
        
        total_pnl_sol = sum(t.get("pnl_sol", 0) for t in sells)
        
        return {
            "total_trades": len(self.history),
            "buys": len(buys),
            "sells": len(sells),
            "total_sol_spent": total_sol_spent,
            "total_sol_received": total_sol_received,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / len(sells) * 100) if sells else 0,
            "total_pnl_sol": total_pnl_sol,
            "open_positions": len([p for p in self.positions.values() if p["total_tokens"] > 0])
        }
    
    def generate_html(self):
        stats = self.get_stats()
        
        trades_html = ""
        for i, trade in enumerate(reversed(self.history), 1):  # Most recent first
            if trade["action"] == "BUY":
                row_class = "buy-row"
                pnl_cell = '<td>-</td><td>-</td>'
                sol_cell = f'-{trade["sol_amount"]:.4f}'
            else:
                row_class = "sell-row"
                pnl = trade.get("pnl_sol", 0)
                pnl_pct = trade.get("pnl_pct", 0)
                pnl_color = "green" if pnl >= 0 else "red"
                pnl_cell = f'<td style="color: {pnl_color}">{pnl:+.4f}</td><td style="color: {pnl_color}">{pnl_pct:+.1f}%</td>'
                sol_cell = f'+{trade["sol_amount"]:.4f}'
            
            trades_html += f'''
            <tr class="{row_class}">
                <td>{trade["timestamp"].strftime("%m/%d %H:%M:%S")}</td>
                <td class="{trade["action"].lower()}">{trade["action"]}</td>
                <td title="{trade["token"]}">{trade["token_symbol"]}</td>
                <td>{trade["token_amount"]:,.2f}</td>
                <td>{sol_cell}</td>
                <td>${trade["value_usd"]:.2f}</td>
                {pnl_cell}
                <td><a href="https://solscan.io/tx/{trade["tx"]}" target="_blank">🔗</a></td>
            </tr>
            '''
        
        if not trades_html:
            trades_html = '<tr><td colspan="9">Waiting for trades...</td></tr>'
        
        # Open positions
        positions_html = ""
        for mint, pos in self.positions.items():
            if pos["total_tokens"] > 0:
                positions_html += f'''
                <tr>
                    <td>{pos["symbol"]}</td>
                    <td>{pos["name"][:20]}</td>
                    <td>{pos["total_tokens"]:,.2f}</td>
                    <td>{pos["total_sol_spent"]:.4f} SOL</td>
                </tr>
                '''
        
        if not positions_html:
            positions_html = '<tr><td colspan="4">No open positions</td></tr>'
        
        runtime = datetime.now() - self.start_time
        hours = int(runtime.total_seconds() // 3600)
        minutes = int((runtime.total_seconds() % 3600) // 60)
        
        pnl_color = "green" if stats["total_pnl_sol"] >= 0 else "red"
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Wallet Tracker - {WALLET[:8]}...</title>
            <meta http-equiv="refresh" content="10">
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; background: #0f0f23; color: #e0e0e0; padding: 20px; margin: 0; }}
                .container {{ max-width: 1400px; margin: 0 auto; }}
                h1 {{ color: #00d4ff; text-align: center; margin-bottom: 5px; }}
                .wallet {{ text-align: center; color: #888; margin-bottom: 20px; font-size: 12px; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 25px; }}
                .stat-card {{ background: #1a1a2e; padding: 15px; border-radius: 8px; border: 1px solid #2a2a3e; text-align: center; }}
                .stat-label {{ color: #888; font-size: 11px; text-transform: uppercase; }}
                .stat-value {{ font-size: 20px; font-weight: bold; margin-top: 5px; }}
                table {{ width: 100%; border-collapse: collapse; background: #1a1a2e; margin-bottom: 20px; border-radius: 8px; overflow: hidden; }}
                th {{ background: #2a2a3e; padding: 10px; text-align: left; font-weight: 600; color: #00d4ff; font-size: 12px; }}
                td {{ padding: 8px 10px; border-bottom: 1px solid #2a2a3e; font-size: 12px; }}
                tr:hover {{ background: #252540; }}
                .buy {{ color: #00ff88; font-weight: bold; }}
                .sell {{ color: #ff4444; font-weight: bold; }}
                .buy-row {{ border-left: 3px solid #00ff88; }}
                .sell-row {{ border-left: 3px solid #ff4444; }}
                a {{ color: #00d4ff; text-decoration: none; }}
                h2 {{ color: #00d4ff; margin-top: 30px; margin-bottom: 15px; font-size: 16px; }}
                .live {{ display: inline-block; width: 8px; height: 8px; background: #00ff88; border-radius: 50%; animation: pulse 2s infinite; margin-right: 8px; }}
                @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}
                .timestamp {{ color: #666; font-size: 10px; text-align: center; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1><span class="live"></span>Wallet Tracker</h1>
                <div class="wallet">{WALLET}</div>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-label">Total Trades</div>
                        <div class="stat-value">{stats["total_trades"]}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Buys / Sells</div>
                        <div class="stat-value">{stats["buys"]} / {stats["sells"]}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Win Rate</div>
                        <div class="stat-value">{stats["win_rate"]:.1f}%</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Total P/L</div>
                        <div class="stat-value" style="color: {pnl_color}">{stats["total_pnl_sol"]:+.4f} SOL</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">SOL Spent</div>
                        <div class="stat-value">{stats["total_sol_spent"]:.2f}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">SOL Received</div>
                        <div class="stat-value">{stats["total_sol_received"]:.2f}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Open Positions</div>
                        <div class="stat-value">{stats["open_positions"]}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Runtime</div>
                        <div class="stat-value">{hours}h {minutes}m</div>
                    </div>
                </div>
                
                <h2>📈 Trade History (His Actual Trades)</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Action</th>
                            <th>Token</th>
                            <th>Amount</th>
                            <th>SOL</th>
                            <th>Value</th>
                            <th>P/L (SOL)</th>
                            <th>P/L %</th>
                            <th>TX</th>
                        </tr>
                    </thead>
                    <tbody>{trades_html}</tbody>
                </table>
                
                <h2>💼 His Open Positions</h2>
                <table>
                    <thead>
                        <tr><th>Symbol</th><th>Name</th><th>Tokens</th><th>Cost Basis</th></tr>
                    </thead>
                    <tbody>{positions_html}</tbody>
                </table>
                
                <div class="timestamp">Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | Refreshes every 10s</div>
            </div>
        </body>
        </html>
        '''
        return html


def start_web_server():
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass
    
    server = HTTPServer(('0.0.0.0', 2020), Handler)
    print(f"🌐 Web dashboard: http://localhost:2020/results.html")
    server.serve_forever()


def main():
    print("=" * 60)
    print("📊 WALLET TRACKER - Live Data Collection")
    print("=" * 60)
    print(f"👀 Tracking: {WALLET}")
    print(f"⏱️  Check interval: {CHECK_INTERVAL}s")
    print("=" * 60)
    
    web_thread = Thread(target=start_web_server, daemon=True)
    web_thread.start()
    time.sleep(1)
    
    tracker = WalletTracker()
    iteration = 0
    
    # Initial sync - mark existing trades as seen
    print("🔄 Syncing existing trades...")
    try:
        initial_trades = get_wallet_trades()
        for trade in initial_trades:
            tx_sig = trade.get("tx", "")
            if tx_sig:
                tracker.seen_txs.add(tx_sig)
        print(f"✅ Ignoring {len(tracker.seen_txs)} historical trades")
        print(f"🎯 Now tracking NEW trades only\n")
    except Exception as e:
        print(f"⚠️  Sync error: {e}\n")
    
    try:
        while True:
            iteration += 1
            
            try:
                trades = get_wallet_trades()
                new_trades = 0
                
                for trade in reversed(trades):
                    result = tracker.process_trade(trade)
                    if result:
                        new_trades += 1
                        action = result["action"]
                        symbol = result["token_symbol"]
                        sol = result["sol_amount"]
                        
                        if action == "BUY":
                            print(f"🟢 BUY  {symbol} | {sol:.4f} SOL | ${result['value_usd']:.2f}")
                            analysis = result.get("analysis")
                            if analysis:
                                print(f"   MC: ${analysis['market_cap']:,.0f} | Liq: ${analysis['liquidity']:,.0f} | Age: {analysis['age_seconds']//60}m")
                        else:
                            pnl = result.get("pnl_sol", 0)
                            pnl_pct = result.get("pnl_pct", 0)
                            emoji = "✅" if pnl >= 0 else "❌"
                            print(f"🔴 SELL {symbol} | {sol:.4f} SOL | P/L: {pnl:+.4f} SOL ({pnl_pct:+.1f}%) {emoji}")
                
                if new_trades == 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No new trades", end="\r")
                else:
                    stats = tracker.get_stats()
                    print(f"📊 Total: {stats['total_trades']} trades | P/L: {stats['total_pnl_sol']:+.4f} SOL | Win: {stats['win_rate']:.1f}%\n")
                
                # Save data
                html = tracker.generate_html()
                with open("results.html", "w", encoding="utf-8") as f:
                    f.write(html)
                
                with open("trade_history.json", "w", encoding="utf-8") as f:
                    json.dump(tracker.history, f, indent=2, default=str)
                
            except Exception as e:
                print(f"❌ Error: {e}")
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        stats = tracker.get_stats()
        print("\n" + "=" * 60)
        print("⏹️  STOPPED")
        print("=" * 60)
        print(f"📊 Total trades: {stats['total_trades']}")
        print(f"💰 Total P/L: {stats['total_pnl_sol']:+.4f} SOL")
        print(f"🎯 Win rate: {stats['win_rate']:.1f}%")
        print(f"📄 Data saved to: trade_history.json")
        print("=" * 60)


if __name__ == "__main__":
    main()
