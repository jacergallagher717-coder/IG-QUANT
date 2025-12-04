import json
import os
from datetime import datetime
from typing import Dict, Optional
from polygon_client import PolygonOptionsClient

class IVTracker:
    def __init__(self, api_key: str):
        self.client = PolygonOptionsClient(api_key)
        self.data_file = "iv_history.json"
        self.history = self._load()
    
    def _load(self) -> Dict:
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.history, f)
    
    def record(self, ticker: str, iv: float):
        ticker = ticker.upper()
        if ticker not in self.history:
            self.history[ticker] = []
        today = datetime.now().strftime('%Y-%m-%d')
        dates = [x['date'] for x in self.history[ticker]]
        if today not in dates:
            self.history[ticker].append({'date': today, 'iv': iv})
            self.history[ticker] = self.history[ticker][-365:]
            self._save()
    
    def get_iv_rank(self, ticker: str, current_iv: float) -> Optional[float]:
        ticker = ticker.upper()
        if ticker not in self.history or len(self.history[ticker]) < 5:
            return None
        ivs = [x['iv'] for x in self.history[ticker]]
        hi, lo = max(ivs), min(ivs)
        if hi == lo:
            return 50.0
        return round((current_iv - lo) / (hi - lo) * 100, 1)
    
    def analyze(self, ticker: str, include_hv: bool = False) -> Dict:
        ticker = ticker.upper()
        iv, price = self.client.get_atm_iv(ticker)

        if iv is None:
            return {'ticker': ticker, 'error': 'Could not get IV'}

        iv_pct = round(iv * 100, 2)

        # HV requires stock data (separate subscription) - skip by default
        hv20_pct = None
        hv60_pct = None
        iv_hv = None
        if include_hv:
            hv20 = self.client.get_hv(ticker, 20)
            hv60 = self.client.get_hv(ticker, 60)
            hv20_pct = round(hv20 * 100, 2) if hv20 else None
            hv60_pct = round(hv60 * 100, 2) if hv60 else None
            iv_hv = round(iv / hv20, 2) if hv20 else None

        self.record(ticker, iv_pct)
        iv_rank = self.get_iv_rank(ticker, iv_pct)

        # Estimate IV rank if we don't have enough history
        estimated = False
        if iv_rank is None:
            # Use 50 as baseline if no history
            iv_rank = 50.0
            estimated = True

        if iv_rank > 70:
            signal = 'SELL_PREMIUM'
        elif iv_rank < 30:
            signal = 'BUY_PREMIUM'
        else:
            signal = 'NEUTRAL'

        return {
            'ticker': ticker,
            'price': round(price, 2) if price else None,
            'iv': iv_pct,
            'hv20': hv20_pct,
            'hv60': hv60_pct,
            'iv_hv': iv_hv,
            'iv_rank': iv_rank,
            'iv_rank_est': estimated,
            'signal': signal,
            'history_days': len(self.history.get(ticker, []))
        }
