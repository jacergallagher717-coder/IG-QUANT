import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time

class PolygonOptionsClient:
    BASE_URL = "https://api.polygon.io"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self._last_call = 0
    
    def _request(self, endpoint: str, params: Dict = None) -> Dict:
        elapsed = time.time() - self._last_call
        if elapsed < 0.12:
            time.sleep(0.12 - elapsed)
        if params is None:
            params = {}
        params['apiKey'] = self.api_key
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            self._last_call = time.time()
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print("Rate limited, waiting 60s...")
                time.sleep(60)
                return self._request(endpoint, params)
            else:
                return {'status': 'ERROR', 'error': response.text}
        except Exception as e:
            return {'status': 'ERROR', 'error': str(e)}
    
    def get_stock_price(self, ticker: str) -> Optional[float]:
        data = self._request(f"/v2/aggs/ticker/{ticker}/prev")
        if data.get('results'):
            return data['results'][0].get('c')
        return None
    
    def get_stock_history(self, ticker: str, days: int = 365) -> pd.DataFrame:
        end = datetime.now()
        start = end - timedelta(days=days)
        data = self._request(f"/v2/aggs/ticker/{ticker}/range/1/day/{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}", {'limit': 50000})
        if data.get('results'):
            df = pd.DataFrame(data['results'])
            df['date'] = pd.to_datetime(df['t'], unit='ms')
            df = df.rename(columns={'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'})
            return df.set_index('date')[['Open', 'High', 'Low', 'Close', 'Volume']]
        return pd.DataFrame()
    
    def get_options_chain(self, ticker: str, strike_gte: float = None, strike_lte: float = None, limit: int = 250) -> pd.DataFrame:
        params = {'limit': limit}
        if strike_gte:
            params['strike_price.gte'] = strike_gte
        if strike_lte:
            params['strike_price.lte'] = strike_lte
        data = self._request(f"/v3/snapshot/options/{ticker}", params)
        if data.get('results'):
            options = []
            for opt in data['results']:
                d = opt.get('details', {})
                g = opt.get('greeks', {})
                day = opt.get('day', {})
                options.append({
                    'type': d.get('contract_type'),
                    'strike': d.get('strike_price'),
                    'expiration': d.get('expiration_date'),
                    'iv': opt.get('implied_volatility'),  # IV is at top level, not in greeks
                    'delta': g.get('delta'),
                    'gamma': g.get('gamma'),
                    'theta': g.get('theta'),
                    'vega': g.get('vega'),
                    'last': day.get('close'),
                    'volume': day.get('volume'),
                    'oi': opt.get('open_interest'),
                    'underlying': opt.get('underlying_asset', {}).get('price'),
                })
            return pd.DataFrame(options)
        return pd.DataFrame()
    
    def get_atm_iv(self, ticker: str) -> Tuple[Optional[float], Optional[float]]:
        price = self.get_stock_price(ticker)
        if not price:
            return None, None
        chain = self.get_options_chain(ticker, strike_gte=price*0.95, strike_lte=price*1.05)
        if chain.empty:
            return None, price
        chain['dist'] = abs(chain['strike'] - price)
        atm = chain.nsmallest(4, 'dist')
        ivs = atm['iv'].dropna()
        if len(ivs) > 0:
            return ivs.mean(), price
        return None, price
    
    def get_hv(self, ticker: str, window: int = 20) -> Optional[float]:
        df = self.get_stock_history(ticker, days=window+10)
        if len(df) < window:
            return None
        returns = np.log(df['Close'] / df['Close'].shift(1)).dropna()
        return returns.tail(window).std() * np.sqrt(252)
