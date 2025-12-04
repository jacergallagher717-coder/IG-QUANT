#!/usr/bin/env python3
"""
OPTIONS EDGE SCANNER
Finds volatility mispricing using real Polygon.io data

Usage:
    python main.py              # Scan default watchlist
    python main.py AAPL NVDA    # Scan specific tickers
"""
import sys
from datetime import datetime
import pandas as pd
from iv_tracker import IVTracker
from polygon_client import PolygonOptionsClient

#############################################
#  PASTE YOUR API KEY BELOW
#############################################
API_KEY = "F7WKp6kqYhOyPglsS1TJvDEC_0L5C3xQ"
#############################################

WATCHLIST = ['SPY', 'QQQ', 'NVDA', 'AAPL', 'TSLA', 'AMD', 'META', 'MSFT', 'GOOGL', 'AMZN']

def get_direction(client, ticker):
    df = client.get_stock_history(ticker, 50)
    if len(df) < 20:
        return 'neutral'
    close = df['Close'].values
    sma20 = pd.Series(close).rolling(20).mean().iloc[-1]
    sma50 = pd.Series(close).rolling(50).mean().iloc[-1] if len(df) >= 50 else sma20
    if close[-1] > sma20 and sma20 > sma50:
        return 'bullish'
    elif close[-1] < sma20 and sma20 < sma50:
        return 'bearish'
    return 'neutral'

def get_strategy(signal, direction):
    if signal == 'SELL_PREMIUM':
        if direction == 'bullish':
            return 'PUT CREDIT SPREAD', 'Sell OTM put spread, collect premium'
        elif direction == 'bearish':
            return 'CALL CREDIT SPREAD', 'Sell OTM call spread, collect premium'
        else:
            return 'IRON CONDOR', 'Sell OTM put spread + call spread'
    elif signal == 'BUY_PREMIUM':
        if direction == 'bullish':
            return 'CALL DEBIT SPREAD', 'Buy ATM call, sell OTM call'
        elif direction == 'bearish':
            return 'PUT DEBIT SPREAD', 'Buy ATM put, sell OTM put'
        else:
            return 'LONG STRADDLE', 'Buy ATM call + put, bet on movement'
    return 'NO TRADE', 'Wait for better setup'

def scan(tickers):
    if not API_KEY or API_KEY == "PASTE_YOUR_API_KEY_HERE":
        print("\n ERROR: You need to add your API key!")
        print("   Open main.py and set your Polygon API key")
        print("   Get it from: https://polygon.io/dashboard")
        return

    tracker = IVTracker(API_KEY)
    client = PolygonOptionsClient(API_KEY)
    
    print("\n" + "="*75)
    print("  OPTIONS EDGE SCANNER")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  Using real Polygon.io data")
    print("="*75)
    
    results = []
    for ticker in tickers:
        print(f"\n  Scanning {ticker}...", end="", flush=True)
        try:
            data = tracker.analyze(ticker)
            if 'error' in data:
                print(f" Error: {data['error']}")
                continue
            data['direction'] = get_direction(client, ticker)
            data['strategy'], data['action'] = get_strategy(data['signal'], data['direction'])
            results.append(data)
            print(f" Done - IV:{data['iv']}% Rank:{data['iv_rank']}%")
        except Exception as e:
            print(f" Error: {e}")
    
    if not results:
        print("\n No results. Check your API key and internet connection.")
        return
    
    results.sort(key=lambda x: x.get('iv_rank') or 0, reverse=True)
    
    print("\n" + "="*75)
    print("  SCAN RESULTS (Sorted by IV Rank)")
    print("="*75)
    
    for r in results:
        est = "(est)" if r.get('iv_rank_est') else ""
        
        if r['signal'] == 'SELL_PREMIUM':
            edge = 'SELL PREMIUM [HIGH IV]'
        elif r['signal'] == 'BUY_PREMIUM':
            edge = 'BUY PREMIUM [LOW IV]'
        else:
            edge = 'NEUTRAL'
        
        dir_display = r['direction'].upper()
        
        print(f"""
+===========================================================================+
|  {r['ticker']:6}  |  ${r['price']:<10}  |  {dir_display:<10}                          |
+---------------------------------------------------------------------------+
|  ATM IV:     {r['iv']:>6.1f}%    |  20d HV:    {r['hv20'] or 'N/A':>6}%   |  60d HV: {r['hv60'] or 'N/A':>6}%  |
|  IV/HV:      {r['iv_hv'] or 'N/A':>6}x    |  IV Rank:   {r['iv_rank'] or 'N/A':>6}% {est:5}                  |
+---------------------------------------------------------------------------+
|  EDGE:       {edge:<25}                              |
|  STRATEGY:   {r['strategy']:<25}                              |
|  ACTION:     {r['action']:<50}   |
|  History:    {r['history_days']} days tracked                                            |
+===========================================================================+""")
    
    print("\n" + "="*75)
    print("  SUMMARY")
    print("="*75)
    
    high_iv = [r['ticker'] for r in results if r['signal'] == 'SELL_PREMIUM']
    low_iv = [r['ticker'] for r in results if r['signal'] == 'BUY_PREMIUM']
    
    print(f"  High IV (Sell Premium): {', '.join(high_iv) if high_iv else 'None'}")
    print(f"  Low IV (Buy Premium):   {', '.join(low_iv) if low_iv else 'None'}")
    
    best = results[0]
    if best['signal'] != 'NEUTRAL':
        print(f"\n  TOP OPPORTUNITY: {best['ticker']}")
        print(f"     IV Rank: {best['iv_rank']}%  |  IV/HV: {best['iv_hv']}x")
        print(f"     Strategy: {best['strategy']}")
        print(f"     {best['action']}")
    
    print("\n  TIP: Run daily to build IV history for accurate IV Rank")
    print("="*75 + "\n")

if __name__ == "__main__":
    tickers = sys.argv[1:] if len(sys.argv) > 1 else WATCHLIST
    scan(tickers)
