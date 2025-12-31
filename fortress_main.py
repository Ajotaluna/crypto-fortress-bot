"""
FortressBot: The Hybrid Titan 🏯🌍
Controller that switches strategies based on Time of Day.
- 00:00 - 09:00 UTC: TOKYO SCALPER (M5, Mean Reversion)
- 09:00 - 00:00 UTC: GLOBAL TREND V5 (H1, Trend Following)
"""
import asyncio
import logging
import sys
import os
import pandas as pd
from datetime import datetime
from config import config
from market_data import MarketData
from scalper_strategy import ScalperStrategy

# Import Trend Logic Components - FROM INTERNAL FORK
# We use the PatternDetector from the internal 'trend_following_bot' directory
from trend_following_bot.patterns import PatternDetector, SentimentAnalyzer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
sys.stdout.reconfigure(line_buffering=True)
logger = logging.getLogger("FortressBot")

class FortressBot:
    def __init__(self, is_dry_run=True, api_key=None, api_secret=None):
        self.market = MarketData(is_dry_run, api_key, api_secret)
        
        # STRATEGY ENGINES
        self.scalper = ScalperStrategy()        # Tokyo Engine
        self.detector = PatternDetector()       # Global Trend Engine
        
        # State
        self.running = True
        self.mode = "UNKNOWN"
        self.blacklist = set() # Simple runtime blacklist for now
        
        # Performance
        self.daily_start_balance = 0.0
        
    async def start(self):
        logger.info(">>> FORTRESS BOT STARTED (HYBRID PROTOCOL) <<<")
        await self.market.initialize_balance()
        self.daily_start_balance = self.market.balance
        
        # Main Loop
        while self.running:
            try:
                await self.tick()
                await asyncio.sleep(60) # 1 Minute Cycle
            except Exception as e:
                logger.error(f"CRITICAL LOOP ERROR: {e}")
                await asyncio.sleep(10)

    async def tick(self):
        """One Heartbeat of the Bot"""
        # 1. DETERMINE TIME & MODE
        current_hour = datetime.utcnow().hour
        
        # 00:00 to 09:00 UTC -> TOKYO SCALPER
        if 0 <= current_hour < 9:
            new_mode = "TOKYO_SCALPER"
        else:
            new_mode = "GLOBAL_TREND"
            
        if new_mode != self.mode:
            logger.info(f"🔄 MODE SWITCH: {self.mode} -> {new_mode}")
            self.mode = new_mode
            
        # 2. MANAGE OPEN POSITIONS
        await self.manage_positions()
        
        # 3. SCAN FOR NEW TRADES (If slots available)
        slots = config.MAX_OPEN_POSITIONS - len(self.market.positions)
        if slots > 0:
            if self.mode == "TOKYO_SCALPER":
                await self.scan_tokyo(slots)
            else:
                await self.scan_global(slots)
        else:
            logger.info(f"Slots Full ({len(self.market.positions)}). Mode: {self.mode}")

    # ==================================================================
    # STRATEGY A: TOKYO SCALPER (00:00 - 09:00 UTC)
    # ==================================================================
    async def scan_tokyo(self, slots):
        """Find short-term mean reversions"""
        logger.info("🏯 TOKYO SCANNER: Hunting M5 Setups...")
        symbols = await self.market.get_top_symbols(limit=30)
        
        for sym in symbols:
            if sym in self.market.positions: continue
            
            # Fetch 5m Data
            df = await self.market.get_klines(sym, interval='5m', limit=100)
            if df.empty: continue
            
            # Analyze
            signal = self.scalper.analyze(df)
            if signal:
                # Execution Logic for Scalper
                # Scalper has Fixed Targets defined in analyze()
                logger.info(f"🏯 SIGNAL FOUND: {sym} {signal['direction']} (Score {signal['score']})")
                
                # Allocation: Smaller size for Scalping? Or Risk Based?
                # Let's use fixed Risk per trade for simplicity implies smaller size if stop is tight
                # But Scalper stops are VERY tight (0.4%), so size might be HUGE if we use 2% Risk.
                # SAFETY: Cap Scalping Risk to 0.5% Account Risk per trade.
                risk_amt = self.market.balance * 0.005 
                stop_dist_pct = abs(signal['entry_price'] - signal['sl']) / signal['entry_price']
                if stop_dist_pct == 0: continue
                
                size_usdt = risk_amt / stop_dist_pct
                
                # Cap max size to 20% of balance to avoid being too heavy
                size_usdt = min(size_usdt, self.market.balance * 0.2)
                
                await self.market.open_position(
                    sym, 
                    signal['direction'], 
                    size_usdt, 
                    signal['sl'], 
                    signal['tp']
                )
                
                slots -= 1
                if slots == 0: break

    # ==================================================================
    # STRATEGY B: GLOBAL TREND SNIPER (09:00 - 00:00 UTC)
    # ==================================================================
    async def scan_global(self, slots):
        """Find high-momentum trend follow setups (Replicated Logic)"""
        logger.info("🌍 GLOBAL SCANNER: Hunting Trend Setups...")
        symbols = await self.market.get_top_symbols(limit=50) # Broader search
        
        # Parallel analysis could go here (omitted for brevity, sequential is safer for V1)
        for sym in symbols:
            if sym in self.market.positions: continue
            
            # Trend Data (15m + 1H context)
            df = await self.market.get_klines(sym, interval=config.TIMEFRAME)
            df_daily = await self.market.get_klines(sym, interval='1d', limit=90)
            if df.empty: continue
            
            # Use Detector
            signal = self.detector.analyze(df, df_daily)
            if not signal: continue
            
            # FILTERS: Weekend Mode (Standard)
            # We stripped the weekday restrictions as requested.
            # Min Score check
            if signal['score'] < config.MIN_SIGNAL_SCORE:
                # Check Override
                is_override = False
                if config.ALLOW_MOMENTUM_OVERRIDE and signal['score'] >= config.MOMENTUM_SCORE_THRESHOLD:
                    is_override = True
                
                if not is_override: continue
            
            # EXECUTION
            # Calculate Dynamic Risk Levels
            sl, tp = self.detector.calculate_dynamic_levels(df, signal['direction'])
            if not sl: continue # Fallback failed
            
            # Sizing: Trend trades take 3% Risk (Standard Config)
            # Implies we trust them more than scalps
            risk_per_trade = config.RISK_PER_TRADE_PCT / 100
            risk_amt = self.market.balance * risk_per_trade
            stop_dist = abs(signal['entry_price'] - sl) / signal['entry_price']
            
            size_usdt = risk_amt / stop_dist
            
            await self.market.open_position(
                sym,
                signal['direction'],
                size_usdt,
                sl,
                tp
            )
            # Mark this position as TREND strategy (important for manager)
            if sym in self.market.positions:
                self.market.positions[sym]['strategy'] = 'GLOBAL_TREND'
            
            slots -= 1
            if slots == 0: break

    # ==================================================================
    # UNIFIED EXECUTION MANAGER
    # ==================================================================
    async def manage_positions(self):
        """Smart Manager that handles Scalps and Trends differently"""
        for sym, pos in list(self.market.positions.items()):
            current_price = await self.market.get_current_price(sym)
            if current_price == 0: continue
            
            # Determine PnL
            if pos['side'] == 'LONG':
                pnl_pct = (current_price - pos['entry_price']) / pos['entry_price']
            else:
                pnl_pct = (pos['entry_price'] - current_price) / pos['entry_price']
            
            # Strategy Type? (Default to TREND if missing)
            strat = pos.get('strategy', 'UNKNOWN')
            if strat == 'UNKNOWN':
                 # Heuristic: If TF was 5m (based on logs) or Tight SL? 
                 # Assume TREND for safety (Trailing Logic is safer than naked hold)
                 strat = 'GLOBAL_TREND'

            # ----------------------------------------------------
            # TYPE A: TOKYO SCALP MANAGEMENT (Fast & Furious)
            # ----------------------------------------------------
            if strat == 'TOKYO_SCALP':
                # Strict Fixed TP/SL
                # TP: 0.6% -> Close ALL
                # SL: 0.4% -> Close ALL
                # Time limit: 45 mins (Don't hold stale scalps)
                
                # Check Time
                duration = (datetime.now() - pos['entry_time']).total_seconds() / 60
                if duration > 60:
                    await self.market.close_position(sym, "TIME LIMIT (Scalp Stale)")
                    continue

                if pnl_pct >= 0.006:
                    await self.market.close_position(sym, "SCALP TP (+0.6%)")
                    continue
                elif pnl_pct <= -0.004:
                    await self.market.close_position(sym, "SCALP SL (-0.4%)")
                    continue
                    
            # ----------------------------------------------------
            # TYPE B: GLOBAL TREND MANAGEMENT (The Harvester)
            # ----------------------------------------------------
            else:
                # 1. Heartbeat
                if self.market.is_dry_run:
                    logger.info(f"💓 {sym} ({strat}): ROI {pnl_pct*100:+.2f}%")
                
                # 2. Hard Limits (Safety)
                if (pos['side'] == 'LONG' and current_price <= pos['sl']) or \
                   (pos['side'] == 'SHORT' and current_price >= pos['sl']):
                    await self.market.close_position(sym, "STOP LOSS")
                    continue
                    
                if (pos['side'] == 'LONG' and current_price >= pos['tp']) or \
                   (pos['side'] == 'SHORT' and current_price <= pos['tp']):
                    await self.market.close_position(sym, "TAKE PROFIT (Full Base)")
                    continue

                # 3. HARVESTER (Partial Profits)
                # Only if NOT already taken
                if not pos.get('partial_taken', False):
                    if pnl_pct >= 0.012: # +1.2% ROI
                         qty_close = pos['amount'] * 0.5
                         await self.market.close_position(sym, "HARVESTER (50%)", params={'qty': qty_close})
                         pos['amount'] -= qty_close
                         pos['partial_taken'] = True
                         pos['be_locked'] = True # Auto lock BE
                         # Move SL to Entry
                         pos['sl'] = pos['entry_price']
                         logger.info(f"🌾 HARVESTED {sym} @ +1.2%")
                
                # 4. BLOODHOUND (Trailing Stop)
                # Only if BE is locked
                if pos.get('be_locked', False):
                    # Simple Trailing: If price moves up, drag SL up
                    # Distance: 1% 
                    trail_dist = current_price * 0.01
                    if pos['side'] == 'LONG':
                        new_sl = current_price - trail_dist
                        if new_sl > pos['sl']:
                            pos['sl'] = new_sl
                            logger.info(f"🐕 TRAILING SL {sym} -> {new_sl:.4f}")
                    else:
                        new_sl = current_price + trail_dist
                        if new_sl < pos['sl']:
                            pos['sl'] = new_sl
                            logger.info(f"🐕 TRAILING SL {sym} -> {new_sl:.4f}")

if __name__ == "__main__":
    api_key = os.getenv('API_KEY')
    api_secret = os.getenv('API_SECRET')
    dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
    
    bot = FortressBot(is_dry_run=dry_run, api_key=api_key, api_secret=api_secret)
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logger.info("Bot Stopped by User")
