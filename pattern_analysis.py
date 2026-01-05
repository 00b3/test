"""
ULTIMATE BOT PATTERN ANALYZER
Analyzes trading patterns from trade_history.json

⚠️ I messed up. I originally made this to test how good that bot is, so I paper-traded it with 0.1 SOL and ran it. Later, I realized we could get all the data from it, so I edited the script to collect that data. However, I forgot to extract his actual buy and sell amounts, so the 1.5 SOL estimate is just a guess based on what I saw on Solscan (he trades around 1–2 SOL per trade).

The P/L percentages are accurate though!
"""
import json
from collections import defaultdict
from datetime import datetime

# His actual trade size (estimated from Solscan - he trades ~1-2 SOL)
HIS_SOL_PER_TRADE = 1.5
YOUR_SOL_PER_TRADE = 0.1
MULTIPLIER = HIS_SOL_PER_TRADE / YOUR_SOL_PER_TRADE

def safe_get(data, key, default=0):
    val = data.get(key, default) if data else default
    return val if val is not None else default

def load_data():
    try:
        with open("trade_history.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ trade_history.json not found!")
        return None
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return None

def group_trades_by_token(history):
    tokens = defaultdict(lambda: {'buys': [], 'sells': [], 'ca': None, 'name': None, 'symbol': None})
    for t in history:
        token_ca = t.get('token')
        symbol = t.get('token_symbol', 'Unknown')
        name = t.get('token_name', 'Unknown')
        if not token_ca:
            continue
        tokens[token_ca]['ca'] = token_ca
        tokens[token_ca]['name'] = name
        tokens[token_ca]['symbol'] = symbol
        if t.get('action') == 'BUY':
            tokens[token_ca]['buys'].append(t)
        else:
            tokens[token_ca]['sells'].append(t)
    return tokens

def analyze_buy_criteria(buys):
    """Analyze WHY he buys - what are his entry criteria"""
    if not buys:
        return {}
    
    buys_with_analysis = [b for b in buys if b.get('analysis')]
    if not buys_with_analysis:
        return {}
    
    # Extract all metrics
    ages = [safe_get(b['analysis'], 'age_seconds') for b in buys_with_analysis]
    ages = [a for a in ages if a > 0]
    
    mcs = [safe_get(b['analysis'], 'market_cap') for b in buys_with_analysis]
    mcs = [m for m in mcs if m and m > 0]
    
    liqs = [safe_get(b['analysis'], 'liquidity') for b in buys_with_analysis]
    liqs = [l for l in liqs if l and l > 0]
    
    holders = [safe_get(b['analysis'], 'holders') for b in buys_with_analysis]
    holders = [h for h in holders if h and h > 0]
    
    ratios = [safe_get(b['analysis'], 'buy_sell_ratio') for b in buys_with_analysis]
    ratios = [r for r in ratios if r and r > 0]
    
    lp_burns = [safe_get(b['analysis'], 'lp_burned') for b in buys_with_analysis]
    lp_burns = [l for l in lp_burns if l is not None]
    
    price_1m = [safe_get(b['analysis'], 'price_change_1m') for b in buys_with_analysis]
    price_5m = [safe_get(b['analysis'], 'price_change_5m') for b in buys_with_analysis]
    price_1h = [safe_get(b['analysis'], 'price_change_1h') for b in buys_with_analysis]
    
    top10 = [safe_get(b['analysis'], 'top10_holders_pct') for b in buys_with_analysis]
    top10 = [t for t in top10 if t and t > 0]
    
    snipers = [safe_get(b['analysis'], 'sniper_count') for b in buys_with_analysis]
    
    no_freeze = sum(1 for b in buys_with_analysis if b['analysis'].get('freeze_authority') is None)
    no_mint = sum(1 for b in buys_with_analysis if b['analysis'].get('mint_authority') is None)
    
    return {
        'age_min': min(ages) if ages else 0,
        'age_max': max(ages) if ages else 0,
        'age_avg': sum(ages)/len(ages) if ages else 0,
        'mc_min': min(mcs) if mcs else 0,
        'mc_max': max(mcs) if mcs else 0,
        'mc_avg': sum(mcs)/len(mcs) if mcs else 0,
        'liq_min': min(liqs) if liqs else 0,
        'liq_max': max(liqs) if liqs else 0,
        'liq_avg': sum(liqs)/len(liqs) if liqs else 0,
        'holders_min': min(holders) if holders else 0,
        'holders_max': max(holders) if holders else 0,
        'holders_avg': sum(holders)/len(holders) if holders else 0,
        'ratio_avg': sum(ratios)/len(ratios) if ratios else 0,
        'lp_burn_avg': sum(lp_burns)/len(lp_burns) if lp_burns else 0,
        'price_1m_avg': sum(price_1m)/len(price_1m) if price_1m else 0,
        'price_5m_avg': sum(price_5m)/len(price_5m) if price_5m else 0,
        'price_1h_avg': sum(price_1h)/len(price_1h) if price_1h else 0,
        'top10_avg': sum(top10)/len(top10) if top10 else 0,
        'sniper_avg': sum(snipers)/len(snipers) if snipers else 0,
        'no_freeze_pct': no_freeze/len(buys_with_analysis)*100 if buys_with_analysis else 0,
        'no_mint_pct': no_mint/len(buys_with_analysis)*100 if buys_with_analysis else 0,
    }

def analyze_sell_criteria(sells, buys):
    """Analyze WHY he sells - what triggers his exits"""
    if not sells:
        return {}
    
    sells_with_analysis = [s for s in sells if s.get('analysis')]
    if not sells_with_analysis:
        return {}
    
    # Calculate hold times and MC changes
    hold_times = []
    mc_changes = []
    price_at_sell_1m = []
    price_at_sell_5m = []
    
    for sell in sells:
        sell_time_str = sell.get('timestamp')
        token = sell.get('token')
        sell_mc = safe_get(sell.get('analysis'), 'market_cap', 0)
        
        # Find matching buy
        for b in buys:
            if b.get('token') == token:
                try:
                    buy_time = datetime.fromisoformat(str(b.get('timestamp')))
                    sell_time = datetime.fromisoformat(str(sell_time_str))
                    if buy_time < sell_time:
                        hold_times.append((sell_time - buy_time).total_seconds())
                        buy_mc = safe_get(b.get('analysis'), 'market_cap', 0)
                        if buy_mc > 0 and sell_mc > 0:
                            mc_changes.append((sell_mc / buy_mc - 1) * 100)
                        break
                except:
                    pass
        
        price_at_sell_1m.append(safe_get(sell.get('analysis'), 'price_change_1m', 0))
        price_at_sell_5m.append(safe_get(sell.get('analysis'), 'price_change_5m', 0))
    
    # Analyze profitable vs losing sells
    profitable_sells = [s for s in sells if (s.get('pnl_pct') or s.get('your_pnl_pct') or 0) > 0]
    losing_sells = [s for s in sells if (s.get('pnl_pct') or s.get('your_pnl_pct') or 0) <= 0]
    
    return {
        'hold_time_avg': sum(hold_times)/len(hold_times)/60 if hold_times else 0,
        'hold_time_min': min(hold_times)/60 if hold_times else 0,
        'hold_time_max': max(hold_times)/60 if hold_times else 0,
        'mc_change_avg': sum(mc_changes)/len(mc_changes) if mc_changes else 0,
        'price_1m_at_sell': sum(price_at_sell_1m)/len(price_at_sell_1m) if price_at_sell_1m else 0,
        'price_5m_at_sell': sum(price_at_sell_5m)/len(price_at_sell_5m) if price_at_sell_5m else 0,
        'profitable_count': len(profitable_sells),
        'losing_count': len(losing_sells),
    }

def analyze_token_trades(token_data):
    buys = sorted(token_data['buys'], key=lambda x: x.get('timestamp', ''))
    sells = sorted(token_data['sells'], key=lambda x: x.get('timestamp', ''))
    
    completed_trades = []
    matched_buy_indices = set()
    
    for sell in sells:
        sell_time_str = sell.get('timestamp')
        pnl_pct = sell.get('pnl_pct') or sell.get('your_pnl_pct') or 0
        pnl_usd = sell.get('pnl_usd') or sell.get('your_pnl_usd') or 0
        sell_analysis = sell.get('analysis', {})
        
        try:
            sell_time = datetime.fromisoformat(str(sell_time_str))
        except:
            continue
        
        # Find matching buy (FIFO)
        best_buy = None
        best_buy_idx = None
        best_buy_time = None
        
        for idx, b in enumerate(buys):
            if idx in matched_buy_indices:
                continue
            try:
                buy_time = datetime.fromisoformat(str(b.get('timestamp')))
                if buy_time >= sell_time:
                    continue
                if best_buy_time is None or buy_time < best_buy_time:
                    best_buy = b
                    best_buy_idx = idx
                    best_buy_time = buy_time
            except:
                continue
        
        if best_buy is not None:
            matched_buy_indices.add(best_buy_idx)
            buy_analysis = best_buy.get('analysis', {})
            
            completed_trades.append({
                'buy_time': best_buy.get('timestamp'),
                'sell_time': sell_time_str,
                'buy_mc': safe_get(buy_analysis, 'market_cap', 0),
                'sell_mc': safe_get(sell_analysis, 'market_cap', 0),
                'buy_holders': safe_get(buy_analysis, 'holders', 0),
                'sell_holders': safe_get(sell_analysis, 'holders', 0),
                'buy_liq': safe_get(buy_analysis, 'liquidity', 0),
                'sell_liq': safe_get(sell_analysis, 'liquidity', 0),
                'buy_age': safe_get(buy_analysis, 'age_seconds', 0),
                'buy_price_1m': safe_get(buy_analysis, 'price_change_1m', 0),
                'buy_price_5m': safe_get(buy_analysis, 'price_change_5m', 0),
                'buy_price_1h': safe_get(buy_analysis, 'price_change_1h', 0),
                'sell_price_1m': safe_get(sell_analysis, 'price_change_1m', 0),
                'sell_price_5m': safe_get(sell_analysis, 'price_change_5m', 0),
                'buy_ratio': safe_get(buy_analysis, 'buy_sell_ratio', 0),
                'pnl_pct': pnl_pct,
                'pnl_usd': pnl_usd,
            })
    
    return {
        'completed': completed_trades,
        'open_count': len(buys) - len(matched_buy_indices),
    }

def analyze_patterns():
    history = load_data()
    if not history:
        return
    
    buys = [t for t in history if t.get('action') == 'BUY']
    sells = [t for t in history if t.get('action') == 'SELL']
    
    print("\n" + "=" * 100)
    print("🔍 ULTIMATE BOT PATTERN ANALYSIS")
    print("=" * 100)
    
    # Group by token and analyze
    tokens = group_trades_by_token(history)
    all_completed = []
    total_open = 0
    
    for ca, token_data in tokens.items():
        analysis = analyze_token_trades(token_data)
        for trade in analysis['completed']:
            trade['symbol'] = token_data['symbol']
            trade['name'] = token_data['name']
            trade['ca'] = ca
            all_completed.append(trade)
        total_open += analysis['open_count']
    
    # Analyze criteria
    buy_criteria = analyze_buy_criteria(buys)
    sell_criteria = analyze_sell_criteria(sells, buys)
    
    # Generate reports
    generate_markdown_report(all_completed, total_open, tokens, buys, sells, history, buy_criteria, sell_criteria)
    generate_html_report(all_completed, total_open, tokens, buys, sells, history, buy_criteria, sell_criteria)
    
    print(f"📄 Reports saved!")


def generate_markdown_report(completed, open_count, tokens, buys, sells, history, buy_criteria, sell_criteria):
    """Generate comprehensive markdown report"""
    
    your_total_pnl = sum(t['pnl_usd'] for t in completed) if completed else 0
    his_total_pnl = your_total_pnl * MULTIPLIER
    profitable = [t for t in completed if t['pnl_pct'] > 0]
    win_rate = len(profitable) / len(completed) * 100 if completed else 0
    
    md = []
    
    # Header with disclaimer
    md.append("# 🔍 Bot Pattern Analysis Report\n")
    md.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    md.append("\n---\n")
    md.append("## ⚠️ Important Note\n")
    md.append("I messed up. I originally made this to test how good that bot is, so I paper-traded it with 0.1 SOL ")
    md.append("and ran it. Later, I realized we could get all the data from it, so I edited the script to collect ")
    md.append("that data. However, I forgot to extract his actual buy and sell amounts, so the 1.5 SOL estimate is ")
    md.append("just a guess based on what I saw on Solscan (he trades around 1–2 SOL per trade).\n\n")
    md.append("**The P/L percentages are accurate though!**\n")
    
    # Summary
    md.append("\n---\n## 📊 Summary\n")
    md.append(f"- **Total Trades:** {len(history)} (Buys: {len(buys)}, Sells: {len(sells)})\n")
    md.append(f"- **Completed Trades:** {len(completed)}\n")
    md.append(f"- **Open Positions:** {open_count}\n")
    md.append(f"- **Win Rate:** {win_rate:.1f}%\n")
    md.append(f"- **Your P/L (0.1 SOL/trade):** ${your_total_pnl:.2f}\n")
    md.append(f"- **His Est. P/L (~1.5 SOL/trade):** ${his_total_pnl:.2f}\n")
    if history:
        md.append(f"- **Time Range:** {history[0].get('timestamp', 'N/A')[:19]} → {history[-1].get('timestamp', 'N/A')[:19]}\n")
    
    # BUY CRITERIA ANALYSIS
    md.append("\n---\n## 🟢 WHY HE BUYS - Entry Criteria Analysis\n")
    md.append("Based on analysis of all his buy transactions:\n\n")
    
    if buy_criteria:
        md.append("### Token Age at Entry\n")
        md.append(f"- **Min:** {buy_criteria['age_min']//60} min\n")
        md.append(f"- **Max:** {buy_criteria['age_max']//60} min ({buy_criteria['age_max']//3600:.1f} hours)\n")
        md.append(f"- **Average:** {buy_criteria['age_avg']//60:.0f} min\n")
        
        if buy_criteria['age_avg'] < 1800:
            md.append(f"- 🎯 **Pattern:** He's an EARLY BUYER - targets tokens under 30 min old\n")
        elif buy_criteria['age_avg'] < 3600:
            md.append(f"- 🎯 **Pattern:** MOMENTUM TRADER - buys tokens 30-60 min old\n")
        else:
            md.append(f"- 🎯 **Pattern:** LATE BUYER - waits for tokens to mature\n")
        
        md.append("\n### Market Cap at Entry\n")
        md.append(f"- **Min:** ${buy_criteria['mc_min']:,.0f}\n")
        md.append(f"- **Max:** ${buy_criteria['mc_max']:,.0f}\n")
        md.append(f"- **Average:** ${buy_criteria['mc_avg']:,.0f}\n")
        
        if buy_criteria['mc_avg'] < 50000:
            md.append(f"- 🎯 **Pattern:** MICRO CAP HUNTER - targets < $50k MC\n")
        elif buy_criteria['mc_avg'] < 150000:
            md.append(f"- 🎯 **Pattern:** LOW CAP TRADER - targets $50k-$150k MC\n")
        else:
            md.append(f"- 🎯 **Pattern:** MID CAP TRADER - targets > $150k MC\n")
        
        md.append("\n### Liquidity at Entry\n")
        md.append(f"- **Min:** ${buy_criteria['liq_min']:,.0f}\n")
        md.append(f"- **Max:** ${buy_criteria['liq_max']:,.0f}\n")
        md.append(f"- **Average:** ${buy_criteria['liq_avg']:,.0f}\n")
        
        md.append("\n### Holders at Entry\n")
        md.append(f"- **Min:** {buy_criteria['holders_min']:.0f}\n")
        md.append(f"- **Max:** {buy_criteria['holders_max']:.0f}\n")
        md.append(f"- **Average:** {buy_criteria['holders_avg']:.0f}\n")
        
        md.append("\n### Price Momentum at Entry\n")
        md.append(f"- **1m avg:** {buy_criteria['price_1m_avg']:+.1f}%\n")
        md.append(f"- **5m avg:** {buy_criteria['price_5m_avg']:+.1f}%\n")
        md.append(f"- **1h avg:** {buy_criteria['price_1h_avg']:+.1f}%\n")
        
        if buy_criteria['price_5m_avg'] > 5:
            md.append(f"- 🎯 **Pattern:** MOMENTUM CHASER - buys when price is pumping\n")
        elif buy_criteria['price_5m_avg'] < -5:
            md.append(f"- 🎯 **Pattern:** DIP BUYER - buys on red candles\n")
        else:
            md.append(f"- 🎯 **Pattern:** NEUTRAL ENTRY - doesn't care about short-term momentum\n")
        
        md.append("\n### Security Requirements\n")
        md.append(f"- **No Freeze Authority:** {buy_criteria['no_freeze_pct']:.1f}% of buys\n")
        md.append(f"- **No Mint Authority:** {buy_criteria['no_mint_pct']:.1f}% of buys\n")
        md.append(f"- **LP Burn avg:** {buy_criteria['lp_burn_avg']:.1f}%\n")
        md.append(f"- **Top 10 Holders avg:** {buy_criteria['top10_avg']:.1f}%\n")
        md.append(f"- **Snipers avg:** {buy_criteria['sniper_avg']:.1f}\n")
        
        md.append("\n### Buy/Sell Ratio\n")
        md.append(f"- **Average:** {buy_criteria['ratio_avg']:.2f}\n")
        if buy_criteria['ratio_avg'] > 1.2:
            md.append(f"- 🎯 **Pattern:** Buys when there's BUYING PRESSURE (ratio > 1)\n")
        else:
            md.append(f"- 🎯 **Pattern:** Doesn't require strong buying pressure\n")
    
    # SELL CRITERIA ANALYSIS
    md.append("\n---\n## 🔴 WHY HE SELLS - Exit Criteria Analysis\n")
    
    if sell_criteria:
        md.append("\n### Hold Time\n")
        md.append(f"- **Min:** {sell_criteria['hold_time_min']:.1f} min\n")
        md.append(f"- **Max:** {sell_criteria['hold_time_max']:.1f} min ({sell_criteria['hold_time_max']/60:.1f} hours)\n")
        md.append(f"- **Average:** {sell_criteria['hold_time_avg']:.1f} min\n")
        
        if sell_criteria['hold_time_avg'] < 10:
            md.append(f"- 🎯 **Pattern:** SCALPER - holds < 10 min\n")
        elif sell_criteria['hold_time_avg'] < 30:
            md.append(f"- 🎯 **Pattern:** QUICK TRADER - holds 10-30 min\n")
        elif sell_criteria['hold_time_avg'] < 60:
            md.append(f"- 🎯 **Pattern:** SWING TRADER - holds 30-60 min\n")
        else:
            md.append(f"- 🎯 **Pattern:** PATIENT HOLDER - holds > 1 hour\n")
        
        md.append("\n### MC Change at Exit\n")
        md.append(f"- **Average MC change:** {sell_criteria['mc_change_avg']:+.1f}%\n")
        
        md.append("\n### Price Momentum at Exit\n")
        md.append(f"- **1m avg at sell:** {sell_criteria['price_1m_at_sell']:+.1f}%\n")
        md.append(f"- **5m avg at sell:** {sell_criteria['price_5m_at_sell']:+.1f}%\n")
        
        if sell_criteria['price_5m_at_sell'] > 5:
            md.append(f"- 🎯 **Pattern:** SELLS INTO STRENGTH - exits while price is still pumping\n")
        elif sell_criteria['price_5m_at_sell'] < -5:
            md.append(f"- 🎯 **Pattern:** PANIC SELLER - exits on red candles\n")
        else:
            md.append(f"- 🎯 **Pattern:** NEUTRAL EXIT - doesn't time exits based on momentum\n")
        
        md.append("\n### Win/Loss Distribution\n")
        md.append(f"- **Profitable exits:** {sell_criteria['profitable_count']}\n")
        md.append(f"- **Losing exits:** {sell_criteria['losing_count']}\n")
    
    # DETAILED TRADE LOG
    md.append("\n---\n## 📋 Detailed Trade Log\n")
    md.append("| Symbol | CA | Buy Time | Sell Time | Hold | Buy MC | Sell MC | MC Δ | P/L % | His P/L |\n")
    md.append("|--------|-----|----------|-----------|------|--------|---------|------|-------|--------|\n")
    
    for t in sorted(completed, key=lambda x: x['pnl_pct'], reverse=True):
        ca_short = f"`{t['ca'][:8]}...`" if t['ca'] else "N/A"
        
        try:
            buy_dt = datetime.fromisoformat(str(t['buy_time']))
            sell_dt = datetime.fromisoformat(str(t['sell_time']))
            hold_min = (sell_dt - buy_dt).total_seconds() / 60
            buy_time_str = buy_dt.strftime("%m/%d %H:%M")
            sell_time_str = sell_dt.strftime("%m/%d %H:%M")
            hold_str = f"{hold_min:.0f}m"
        except:
            buy_time_str = "N/A"
            sell_time_str = "N/A"
            hold_str = "N/A"
        
        buy_mc = f"${t['buy_mc']:,.0f}" if t['buy_mc'] else "N/A"
        sell_mc = f"${t['sell_mc']:,.0f}" if t['sell_mc'] else "N/A"
        mc_change = ((t['sell_mc'] / t['buy_mc'] - 1) * 100) if t['buy_mc'] > 0 and t['sell_mc'] > 0 else 0
        his_pnl = t['pnl_usd'] * MULTIPLIER
        emoji = "✅" if t['pnl_pct'] > 0 else "❌"
        
        md.append(f"| {t['symbol']} | {ca_short} | {buy_time_str} | {sell_time_str} | {hold_str} | {buy_mc} | {sell_mc} | {mc_change:+.0f}% | {t['pnl_pct']:.1f}% | ${his_pnl:.2f} {emoji} |\n")
    
    # BOT CONFIG
    md.append("\n---\n## ⚙️ Recommended Bot Settings (Based on His Patterns)\n")
    md.append("```python\n")
    md.append("BOT_CONFIG = {\n")
    if buy_criteria:
        md.append(f"    'max_age_minutes': {int(buy_criteria['age_avg']//60 * 1.5)},  # He buys avg {buy_criteria['age_avg']//60:.0f}m old\n")
        md.append(f"    'min_market_cap': {int(buy_criteria['mc_min'])},\n")
        md.append(f"    'max_market_cap': {int(buy_criteria['mc_avg'] * 1.5)},\n")
        md.append(f"    'min_liquidity': {int(buy_criteria['liq_min'])},\n")
        md.append(f"    'min_holders': {int(buy_criteria['holders_min'])},\n")
        md.append(f"    'max_holders': {int(buy_criteria['holders_avg'] * 1.5)},\n")
        md.append(f"    'min_lp_burn': {int(buy_criteria['lp_burn_avg'] - 5)},\n")
        md.append(f"    'require_no_freeze': {buy_criteria['no_freeze_pct'] > 90},\n")
        md.append(f"    'require_no_mint': {buy_criteria['no_mint_pct'] > 90},\n")
    if sell_criteria:
        md.append(f"    'target_hold_minutes': {int(sell_criteria['hold_time_avg'])},\n")
    md.append("}\n")
    md.append("```\n")
    
    with open("analysis_report.md", "w", encoding="utf-8") as f:
        f.write("".join(md))
    
    print(f"📄 Markdown report saved to: analysis_report.md")


def generate_html_report(completed, open_count, tokens, buys, sells, history, buy_criteria, sell_criteria):
    """Generate interactive HTML report"""
    
    your_total_pnl = sum(t['pnl_usd'] for t in completed) if completed else 0
    his_total_pnl = your_total_pnl * MULTIPLIER
    profitable = [t for t in completed if t['pnl_pct'] > 0]
    win_rate = len(profitable) / len(completed) * 100 if completed else 0
    
    # Build trades table
    trades_html = ""
    for t in sorted(completed, key=lambda x: x['pnl_pct'], reverse=True):
        try:
            buy_dt = datetime.fromisoformat(str(t['buy_time']))
            sell_dt = datetime.fromisoformat(str(t['sell_time']))
            hold_min = (sell_dt - buy_dt).total_seconds() / 60
            buy_time_str = buy_dt.strftime("%m/%d %H:%M")
            sell_time_str = sell_dt.strftime("%m/%d %H:%M")
        except:
            buy_time_str = sell_time_str = "N/A"
            hold_min = 0
        
        pnl_class = "profit" if t['pnl_pct'] > 0 else "loss"
        buy_mc = f"${t['buy_mc']:,.0f}" if t['buy_mc'] else "N/A"
        sell_mc = f"${t['sell_mc']:,.0f}" if t['sell_mc'] else "N/A"
        mc_change = ((t['sell_mc'] / t['buy_mc'] - 1) * 100) if t['buy_mc'] > 0 and t['sell_mc'] > 0 else 0
        mc_class = "profit" if mc_change > 0 else "loss"
        his_pnl = t['pnl_usd'] * MULTIPLIER
        emoji = "✅" if t['pnl_pct'] > 0 else "❌"
        
        trades_html += f'''
        <tr class="{pnl_class}-row">
            <td>{t['symbol']}</td>
            <td class="ca-cell" onclick="copyCA('{t['ca']}')">{t['ca'][:6]}...{t['ca'][-4:]}</td>
            <td>{buy_time_str}</td>
            <td>{sell_time_str}</td>
            <td>{hold_min:.0f}m</td>
            <td>{buy_mc}</td>
            <td>{sell_mc}</td>
            <td class="{mc_class}">{mc_change:+.0f}%</td>
            <td>{t['buy_age']//60:.0f}m</td>
            <td>{t['buy_holders']}</td>
            <td class="{pnl_class}">${his_pnl:.2f}</td>
            <td class="{pnl_class}">{t['pnl_pct']:.1f}%</td>
            <td>{emoji}</td>
        </tr>'''
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>🔍 Bot Pattern Analysis</title>
    <meta charset="UTF-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #0f0f23, #1a1a3e); color: #e0e0e0; padding: 20px; min-height: 100vh; }}
        .container {{ max-width: 1600px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; text-align: center; margin-bottom: 10px; }}
        h2 {{ color: #00d4ff; margin: 25px 0 15px 0; font-size: 1.3em; }}
        h3 {{ color: #ffaa00; margin: 15px 0 10px 0; font-size: 1.1em; }}
        .warning {{ background: #442200; border: 1px solid #ffaa00; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .warning-title {{ color: #ffaa00; font-weight: bold; margin-bottom: 10px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 20px 0; }}
        .stat-card {{ background: rgba(26,26,46,0.8); padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #2a2a4e; }}
        .stat-label {{ color: #888; font-size: 11px; text-transform: uppercase; }}
        .stat-value {{ font-size: 20px; font-weight: bold; margin-top: 5px; }}
        .profit {{ color: #00ff88; }}
        .loss {{ color: #ff4444; }}
        .criteria-box {{ background: rgba(26,26,46,0.8); padding: 20px; border-radius: 10px; margin: 15px 0; border: 1px solid #2a2a4e; }}
        .criteria-item {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #2a2a4e; }}
        .criteria-label {{ color: #888; }}
        .criteria-value {{ font-weight: bold; }}
        .pattern {{ background: #1a3a1a; border-left: 3px solid #00ff88; padding: 10px 15px; margin: 10px 0; }}
        table {{ width: 100%; border-collapse: collapse; background: rgba(26,26,46,0.8); border-radius: 10px; overflow: hidden; font-size: 12px; margin: 20px 0; }}
        th {{ background: #2a2a4e; padding: 10px 6px; text-align: left; color: #00d4ff; font-size: 11px; position: sticky; top: 0; }}
        td {{ padding: 8px 6px; border-bottom: 1px solid #2a2a4e; }}
        tr:hover {{ background: rgba(0,212,255,0.1); }}
        .profit-row {{ border-left: 3px solid #00ff88; }}
        .loss-row {{ border-left: 3px solid #ff4444; }}
        .ca-cell {{ font-family: monospace; cursor: pointer; color: #00d4ff; font-size: 11px; }}
        .ca-cell:hover {{ background: #00d4ff; color: #000; border-radius: 3px; }}
        .toast {{ position: fixed; bottom: 20px; right: 20px; background: #00ff88; color: #000; padding: 12px 24px; border-radius: 8px; font-weight: bold; opacity: 0; transition: opacity 0.3s; z-index: 1000; }}
        .toast.show {{ opacity: 1; }}
        .section {{ margin: 30px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Bot Pattern Analysis</h1>
        <p style="text-align:center;color:#888;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="warning">
            <div class="warning-title">⚠️ Important Note</div>
            <p>I messed up. I originally made this to test how good that bot is, so I paper-traded it with 0.1 SOL and ran it. Later, I realized we could get all the data from it, so I edited the script to collect that data. However, I forgot to extract his actual buy and sell amounts, so the 1.5 SOL estimate is just a guess based on what I saw on Solscan (he trades around 1–2 SOL per trade).<strong>The P/L percentages are accurate though!</strong></p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-label">Total Trades</div><div class="stat-value">{len(history)}</div></div>
            <div class="stat-card"><div class="stat-label">Completed</div><div class="stat-value">{len(completed)}</div></div>
            <div class="stat-card"><div class="stat-label">Win Rate</div><div class="stat-value {'profit' if win_rate >= 50 else 'loss'}">{win_rate:.1f}%</div></div>
            <div class="stat-card"><div class="stat-label">His Est. P/L</div><div class="stat-value {'profit' if his_total_pnl >= 0 else 'loss'}">${his_total_pnl:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">Profitable</div><div class="stat-value profit">{len(profitable)}</div></div>
            <div class="stat-card"><div class="stat-label">Losing</div><div class="stat-value loss">{len(completed) - len(profitable)}</div></div>
            <div class="stat-card"><div class="stat-label">Open</div><div class="stat-value">{open_count}</div></div>
        </div>
        
        <div class="section">
            <h2>🟢 WHY HE BUYS - Entry Criteria</h2>
            <div class="criteria-box">
                <h3>Token Age</h3>
                <div class="criteria-item"><span class="criteria-label">Min</span><span class="criteria-value">{buy_criteria.get('age_min',0)//60:.0f} min</span></div>
                <div class="criteria-item"><span class="criteria-label">Max</span><span class="criteria-value">{buy_criteria.get('age_max',0)//60:.0f} min</span></div>
                <div class="criteria-item"><span class="criteria-label">Average</span><span class="criteria-value">{buy_criteria.get('age_avg',0)//60:.0f} min</span></div>
                <div class="pattern">🎯 {'EARLY BUYER - targets tokens < 30 min old' if buy_criteria.get('age_avg',0) < 1800 else 'MOMENTUM TRADER - buys established tokens'}</div>
                
                <h3>Market Cap</h3>
                <div class="criteria-item"><span class="criteria-label">Min</span><span class="criteria-value">${buy_criteria.get('mc_min',0):,.0f}</span></div>
                <div class="criteria-item"><span class="criteria-label">Max</span><span class="criteria-value">${buy_criteria.get('mc_max',0):,.0f}</span></div>
                <div class="criteria-item"><span class="criteria-label">Average</span><span class="criteria-value">${buy_criteria.get('mc_avg',0):,.0f}</span></div>
                <div class="pattern">🎯 {'MICRO CAP HUNTER - targets < $50k' if buy_criteria.get('mc_avg',0) < 50000 else 'LOW/MID CAP TRADER'}</div>
                
                <h3>Price Momentum at Entry</h3>
                <div class="criteria-item"><span class="criteria-label">1m avg</span><span class="criteria-value">{buy_criteria.get('price_1m_avg',0):+.1f}%</span></div>
                <div class="criteria-item"><span class="criteria-label">5m avg</span><span class="criteria-value">{buy_criteria.get('price_5m_avg',0):+.1f}%</span></div>
                <div class="criteria-item"><span class="criteria-label">1h avg</span><span class="criteria-value">{buy_criteria.get('price_1h_avg',0):+.1f}%</span></div>
                
                <h3>Security</h3>
                <div class="criteria-item"><span class="criteria-label">No Freeze</span><span class="criteria-value">{buy_criteria.get('no_freeze_pct',0):.0f}%</span></div>
                <div class="criteria-item"><span class="criteria-label">No Mint</span><span class="criteria-value">{buy_criteria.get('no_mint_pct',0):.0f}%</span></div>
                <div class="criteria-item"><span class="criteria-label">LP Burn avg</span><span class="criteria-value">{buy_criteria.get('lp_burn_avg',0):.0f}%</span></div>
            </div>
        </div>
        
        <div class="section">
            <h2>🔴 WHY HE SELLS - Exit Criteria</h2>
            <div class="criteria-box">
                <h3>Hold Time</h3>
                <div class="criteria-item"><span class="criteria-label">Min</span><span class="criteria-value">{sell_criteria.get('hold_time_min',0):.1f} min</span></div>
                <div class="criteria-item"><span class="criteria-label">Max</span><span class="criteria-value">{sell_criteria.get('hold_time_max',0):.1f} min</span></div>
                <div class="criteria-item"><span class="criteria-label">Average</span><span class="criteria-value">{sell_criteria.get('hold_time_avg',0):.1f} min</span></div>
                <div class="pattern">🎯 {'SCALPER - holds < 10 min' if sell_criteria.get('hold_time_avg',0) < 10 else 'QUICK TRADER - holds 10-30 min' if sell_criteria.get('hold_time_avg',0) < 30 else 'SWING TRADER - holds 30+ min'}</div>
                
                <h3>Exit Timing</h3>
                <div class="criteria-item"><span class="criteria-label">MC Change avg</span><span class="criteria-value">{sell_criteria.get('mc_change_avg',0):+.1f}%</span></div>
                <div class="criteria-item"><span class="criteria-label">1m at sell</span><span class="criteria-value">{sell_criteria.get('price_1m_at_sell',0):+.1f}%</span></div>
                <div class="criteria-item"><span class="criteria-label">5m at sell</span><span class="criteria-value">{sell_criteria.get('price_5m_at_sell',0):+.1f}%</span></div>
            </div>
        </div>
        
        <div class="section">
            <h2>📋 All Trades (Click CA to Copy)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>CA</th>
                        <th>Buy Time</th>
                        <th>Sell Time</th>
                        <th>Hold</th>
                        <th>Buy MC</th>
                        <th>Sell MC</th>
                        <th>MC Δ</th>
                        <th>Age</th>
                        <th>Holders</th>
                        <th>His P/L</th>
                        <th>P/L %</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>{trades_html}</tbody>
            </table>
        </div>
    </div>
    
    <div class="toast" id="toast">✅ CA Copied!</div>
    <script>
        function copyCA(ca) {{
            navigator.clipboard.writeText(ca).then(() => {{
                const toast = document.getElementById('toast');
                toast.classList.add('show');
                setTimeout(() => toast.classList.remove('show'), 2000);
            }});
        }}
    </script>
</body>
</html>'''
    
    with open("analysis_report.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"🌐 HTML report saved to: analysis_report.html")


if __name__ == "__main__":
    analyze_patterns()
