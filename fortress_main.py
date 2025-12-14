"""
Fortress Bot Main (The Brain)
integrates Regime Detection to switch between Trend and Scalping strategies.
"""
import asyncio
import logging
import sys
import pandas as pd
from datetime import datetime
from config import config
from market_data import MarketData
from trend_following_bot.patterns import PatternDetector
from scalping_bot_v2.strategy import ScalperStrategy

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("FortressBot")

class FortressBot:
    def __init__(self, is_dry_run=True, api_key=None, api_secret=None):
        self.market = MarketData(is_dry_run, api_key, api_secret)
        self.trend_detector = PatternDetector()
        self.scalp_strategy = ScalperStrategy()
        
        self.running = True
        self.start_balance = 0.0
        self.current_regime = "UNKNOWN" # 'TRENDING' or 'RANGING'
        self.daily_pnl_pct = 0.0
        
    async def start(self):
        logger.info(">>> FORTRESS BOT STARTED (Regime Detection Active) <<<")
        await self.market.initialize_balance()
        self.start_balance = self.market.balance
        
        await asyncio.gather(
            self.regime_loop(),    # The Brain: Decides Trend vs Range
            self.execution_loop(), # The Arm: Executes based on Regime
            self.safety_loop(),
            self.reporting_loop()
        )

    async def regime_loop(self):
        """Detects Market Regime (BTC/ETH ADX + Trend)"""
        logger.info("Started Regime Detector...")
        while self.running:
            try:
                # Analyze BTC as proxy for market
                df = await self.market.get_klines('BTCUSDT', interval='1h', limit=50)
                if not df.empty:
                    # Calculate ADX and EMA200
                    # For simplicity using pandas if ta-lib not available, or just custom
                    # Here we implement simplified Regime Logic:
                    # Ranging: Volume is dropping AND Price is crossing High/Low
                    # Trending: Price > EMA200 AND Strong Volume
                    
                    # Placeholder for ADX (requires ta-lib in container)
                    # For now: Using Volatility + MA
                    
                    close = df['close']
                    ema_50 = close.ewm(span=50).mean().iloc[-1]
                    ema_200 = close.ewm(span=200).mean().iloc[-1]
                    
                    # Volatility (ATR-like)
                    tr = (df['high'] - df['low']).mean()
                    
                    if close.iloc[-1] > ema_50 and close.iloc[-1] > ema_200:
                        self.current_regime = "TRENDING_UP"
                    elif close.iloc[-1] < ema_50 and close.iloc[-1] < ema_200:
                        self.current_regime = "TRENDING_DOWN"
                    else:
                        self.current_regime = "RANGING"
                        
                    logger.info(f"🛡️ MARKET REGIME: {self.current_regime} | BTC Price: {close.iloc[-1]:.0f}")
                
                await asyncio.sleep(300) # Check every 5m
            except Exception as e:
                logger.error(f"Regime Error: {e}")
                await asyncio.sleep(60)

    async def execution_loop(self):
        """Executes Strategies based on Regime"""
        logger.info("Started Execution Engine...")
        while self.running:
            try:
                if self.current_regime == "UNKNOWN":
                    await asyncio.sleep(10)
                    continue
                
                # SAFETY CIRCUIT BREAKER (-1% Daily)
                if self.daily_pnl_pct <= -1.0:
                    logger.warning("⛔ CIRCUIT BREAKER TRIGGERED: Daily Loss > 1%. SLEEPING 24H.")
                    await asyncio.sleep(86400)
                    self.daily_pnl_pct = 0.0 # Reset after sleep
                    continue

                if "TRENDING" in self.current_regime:
                    # Use Trend Logic (modified Main from TrendBot)
                    # We can call the logic directly or refactor
                    await self.run_trend_logic()
                elif "RANGING" in self.current_regime:
                    # Use Scalping Logic
                    await self.run_scalp_logic()
                
                await asyncio.sleep(60) # Scan loop
            except Exception as e:
                logger.error(f"Execution Error: {e}")
                await asyncio.sleep(10)

    async def run_trend_logic(self):
        """Delegates to Trend Bot Logic"""
        # We instantiate on demand or keep persistent? Persistent is better for state.
        if not hasattr(self, 'trend_bot'):
            from trend_following_bot.main import TrendFollowingBot
            self.trend_bot = TrendFollowingBot(self.market.is_dry_run, self.market.api_key, self.market.api_secret)
            # Share market instance to avoid double connection/rate limits? 
            # Better to reuse self.market if possible, but bots might be coupled to their own.
            # For quick prototype, let them have their own market data but sync balance.
            logger.info("Initialized Sub-Bot: TREND")

        # Run one iteration of the Trend Bot's scan
        # We need to expose a 'tick()' or 'scan()' method in TrendBot instead of infinite loop.
        # Check if TrendBot has a scan method suitable for one-off call.
        # It has scan_and_fill_batch.
        
        # Sync Balance
        self.trend_bot.market.balance = self.market.balance
        
        # Run Scan
        slots = config.MAX_OPEN_POSITIONS - len(self.trend_bot.market.positions)
        if slots > 0:
            await self.trend_bot.scan_and_fill_batch(slots)
            
        # Also run supervision
        await self.trend_bot.safety_loop_tick() # Need to refactor TrendBot to have this
        
    async def run_scalp_logic(self):
        """Delegates to Scalping Bot Logic"""
        if not hasattr(self, 'scalp_bot'):
            from scalping_bot_v2.main import ScalpingBot
            self.scalp_bot = ScalpingBot(self.market.is_dry_run, self.market.api_key, self.market.api_secret)
            logger.info("Initialized Sub-Bot: SCALP")
            
        self.scalp_bot.market.balance = self.market.balance
        # Run Scalp Scan
        await self.scalp_bot.scan_loop_tick() # Need to refactor ScalpBot

    async def safety_loop(self):
        # Same as V4
        pass

    async def reporting_loop(self):
        # Same as V4
        pass

if __name__ == "__main__":
    import os
    api_key = os.getenv('API_KEY')
    api_secret = os.getenv('API_SECRET')
    dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
    
    bot = FortressBot(is_dry_run=dry_run, api_key=api_key, api_secret=api_secret)
    asyncio.run(bot.start())
