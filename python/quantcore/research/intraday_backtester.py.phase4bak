import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

class IntradayBacktester:
    def __init__(self):
        pass

    def run_orb(self, symbol: str, period: str = "5d", interval: str = "5m", orb_minutes: int = 30):
        # Fetch intraday data
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if df.empty:
            return {"error": "No intraday data available."}
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        df = df.reset_index()
        if 'Datetime' in df.columns:
            df['Date'] = df['Datetime'].dt.date
            df['Time'] = df['Datetime'].dt.time
            df['Hour'] = df['Datetime'].dt.hour
            df['Minute'] = df['Datetime'].dt.minute
        else:
            df['Date'] = df.index.date
            df['Time'] = df.index.time
            df['Hour'] = df.index.hour
            df['Minute'] = df.index.minute
            
        trades = []
        equity = [10000.0]
        
        for date, group in df.groupby('Date'):
            # Filter regular hours (approx 9:30 to 15:30 for safety)
            group = group[(group['Hour'] >= 9) & (group['Hour'] < 16)]
            if len(group) < orb_minutes + 5:
                continue
                
            orb = group.iloc[:orb_minutes]
            orb_high = orb['High'].max()
            orb_low = orb['Low'].min()
            
            rest_of_day = group.iloc[orb_minutes:]
            
            entry_price = None
            direction = None
            
            for i, row in rest_of_day.iterrows():
                if entry_price is None:
                    if row['Close'] > orb_high:
                        entry_price = row['Close']
                        direction = "LONG"
                    elif row['Close'] < orb_low:
                        entry_price = row['Close']
                        direction = "SHORT"
                else:
                    exit_price = row['Close']
                    if direction == "LONG":
                        pnl = (exit_price - entry_price) * 10 
                    else:
                        pnl = (entry_price - exit_price) * 10
                        
                    trades.append({
                        "date": str(date),
                        "direction": direction,
                        "entry": entry_price,
                        "exit": exit_price,
                        "pnl": pnl
                    })
                    equity.append(equity[-1] + pnl)
                    break 
                    
        if not trades:
            return {"error": "No ORB setups triggered in the selected period."}
            
        total_trades = len(trades)
        wins = sum(1 for t in trades if t['pnl'] > 0)
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        net_pnl = sum(t['pnl'] for t in trades)
        
        return {
            "symbol": symbol,
            "interval": interval,
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1),
            "net_pnl": round(net_pnl, 2),
            "final_equity": round(equity[-1], 2),
            "equity_curve": [round(e, 2) for e in equity],
            "trades": trades[-5:] 
        }
