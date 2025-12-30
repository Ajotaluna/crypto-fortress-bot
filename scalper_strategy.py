"""
Tokyo Scalper Strategy (The Drifter) 🏯
Optimized for low-volatility Asian ranges (00:00 - 09:00 UTC).
Logic: Mean Reversion using Bollinger Bands + RSI.
"""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger("FortressBot")

class ScalperStrategy:
    def __init__(self):
        # Parameters for Tokyo Range
        self.rsi_period = 14
        self.bb_period = 20
        self.bb_std = 2.0
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        
    def analyze(self, df):
        """
        Analyze 5m candles for scalping signals.
        Returns dict: {'direction': 'LONG'/'SHORT', 'score': 0-100, 'sl': price, 'tp': price} or None
        """
        if df.empty or len(df) < 50: return None
        
        # Calculate Indicators
        close = df['close']
        
        # 1. RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # 2. Bollinger Bands
        sma = close.rolling(window=self.bb_period).mean()
        std = close.rolling(window=self.bb_period).std()
        upper_bb = sma + (std * self.bb_std)
        lower_bb = sma - (std * self.bb_std)
        
        # Get latest values
        current_price = close.iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_upper = upper_bb.iloc[-1]
        current_lower = lower_bb.iloc[-1]
        
        # SIGNAL LOGIC: Reversion to Mean
        signal = None
        
        # LONG: Price Touched Lower Band AND RSI Oversold
        if current_price <= current_lower and current_rsi < self.rsi_oversold:
            signal = 'LONG'
            score = 85 # Base score for this setup
            
            # Boost score if extreme RSI
            if current_rsi < 25: score += 10
            
            # TP/SL Targets (Tight for Scalping)
            # TP: Middle Band (SMA) or Fixed %
            # SL: Recent Low or Fixed %
            tp_price = current_price * 1.006 # +0.6%
            sl_price = current_price * 0.996 # -0.4%
            
        # SHORT: Price Touched Upper Band AND RSI Overbought
        elif current_price >= current_upper and current_rsi > self.rsi_overbought:
            signal = 'SHORT'
            score = 85
            
            if current_rsi > 75: score += 10
            
            tp_price = current_price * 0.994 # -0.6%
            sl_price = current_price * 1.004 # +0.4%
            
        if signal:
            return {
                'direction': signal,
                'score': score,
                'entry_price': current_price,
                'tp': tp_price,
                'sl': sl_price,
                'strategy': 'TOKYO_SCALP'
            }
            
        return None
