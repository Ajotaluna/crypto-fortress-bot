"""
Scalping Bot V2 - MAIN
Sub-second monitoring loop.
"""
import asyncio
import logging
import sys
from config import config
from market_data import MarketData
from strategy import ScalperStrategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("ScalperV2")

import concurrent.futures
from datetime import datetime

class ScalpingBot:
    def __init__(self, is_dry_run=True, api_key=None, api_secret=None):
        self.market = MarketData(is_dry_run, api_key, api_secret)
        self.strategy = ScalperStrategy()
        self.running = True
        self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=4)
        self.start_balance = self.market.balance

    def __del__(self):
        self.executor.shutdown(wait=False)
        
    async def start(self):
        logger.info(">>> SCALPING BOT V2 STARTED <<<")
        logger.info(f"Fee Settings: Maker {config.CALC_FEE_MAKER*100}% | Taker {config.CALC_FEE_TAKER*100}%")
        await asyncio.gather(self.fast_loop(), self.scan_loop(), self.reporting_loop())
        
    async def reporting_loop(self):
        """REPORTING LOOP: Logs Status Loop (Every 5m)"""
        logger.info("Started Status Reporter...")
        while self.running:
            try:
                # 0. Check Total Equity (Balance + PnL)
                unrealized_pnl = 0.0
                if self.market.positions:
                    for sym, pos in self.market.positions.items():
                        # Rough estimate for reporting
                        curr_price = await self.market.get_current_price(sym)
                        if curr_price > 0:
                            entry = pos['entry_price']
                            qty = pos.get('amount', 0)
                            if pos['side'] == 'LONG':
                                unrealized_pnl += (curr_price - entry) * qty
                            else:
                                unrealized_pnl += (entry - curr_price) * qty

                total_equity = self.market.balance + unrealized_pnl
                current_pnl_pct = ((total_equity - self.start_balance) / self.start_balance) * 100
                
                # Log Status
                if self.market.positions:
                    logger.info(f"--- STATUS REPORT (Total Equity: {total_equity:.2f} | PnL: {current_pnl_pct:.2f}%) ---")
                    for sym, pos in self.market.positions.items():
                        curr_price = await self.market.get_current_price(sym)
                        pnl = 0.0
                        if curr_price > 0:
                            entry = pos['entry_price']
                            if pos['side'] == 'LONG':
                                pnl = (curr_price - entry) / entry * 100
                            else:
                                pnl = (entry - curr_price) / entry * 100
                        
                        duration_min = (datetime.now() - pos['entry_time']).total_seconds() / 60
                        logger.info(f"{sym} {pos['side']} | PnL: {pnl:.2f}% | Time: {duration_min:.1f}m")
                else:
                    logger.info(f"--- STATUS REPORT: No Open Positions (PnL: {current_pnl_pct:.2f}%) ---")

                if current_pnl_pct >= config.DAILY_PROFIT_TARGET_PCT:
                    logger.info(f"DAILY TARGET REACHED! PnL: +{current_pnl_pct:.2f}%")
                    self.running = False
                    break
                
                await asyncio.sleep(300) # 5 minutes
                
            except Exception as e:
                logger.error(f"Reporting Loop Error: {e}")
                await asyncio.sleep(60)
        
    async def fast_loop(self):
        """Sub-second monitor for exits"""
        while self.running:
            for symbol, pos in list(self.market.positions.items()):
                price = await self.market.get_current_price(symbol)
                if price == 0: continue
                
                # Check Duration
                duration_sec = (datetime.now() - pos['entry_time']).total_seconds()
                
                # Calculate ROI
                if pos['side'] == 'LONG':
                    roi = ((price - pos['entry_price']) / pos['entry_price']) * config.LEVERAGE * 100
                else:
                    roi = ((pos['entry_price'] - price) / pos['entry_price']) * config.LEVERAGE * 100
                
                # Update Max ROI for Trailing
                if roi > pos['max_roi']: pos['max_roi'] = roi
                
                # 1. Stop Loss
                if roi <= config.STOP_LOSS_ROI:
                    await self.market.close_position(symbol, f"STOP LOSS ({roi:.2f}%)")
                    continue
                    
                # 2. Take Profit
                if roi >= config.TAKE_PROFIT_ROI:
                    await self.market.close_position(symbol, f"TAKE PROFIT ({roi:.2f}%)")
                    continue
                    
                # 3. Trailing Stop
                if config.USE_TRAILING and pos['max_roi'] >= config.TRAILING_ACTIVATION_ROI:
                    if roi < (pos['max_roi'] - config.TRAILING_DISTANCE_ROI):
                        await self.market.close_position(symbol, f"TRAILING STOP (Max {pos['max_roi']:.2f}%)")
                        continue

                # 4. Stagnation Exit (Opportunity Cost)
                if duration_sec > 600 and roi < 2.0:
                    await self.market.close_position(symbol, f"STAGNATION (Time {duration_sec/60:.1f}m)")
                    continue

                # 5. Max Time Limit
                if duration_sec > config.MAX_HOLD_SECONDS:
                    await self.market.close_position(symbol, "MAX TIME LIMIT")
                        
            await asyncio.sleep(config.CHECK_INTERVAL)

    async def scan_loop(self):
        """SCANNING LOOP: Finds Opportunities"""
        logger.info("Started Scalp Scanner...")
        while self.running:
            await self.scan_loop_tick()
            await asyncio.sleep(config.SCAN_INTERVAL)

    async def scan_loop_tick(self):
        """Single iteration of Scalp Scanner"""
        try:
            # 1. Check open slots
            if len(self.market.positions) >= config.MAX_OPEN_POSITIONS:
                return

            symbols = await self.market.get_top_vol_symbols()
            
            loop = asyncio.get_running_loop()
            
            pending_symbols = []
            for symbol in symbols[:30]:
                if symbol in self.market.positions: continue
                pending_symbols.append(symbol)
            
            if not pending_symbols: return

            # 2. Parallel Analysis
            scan_candidates = []
            for symbol in pending_symbols:
                df = await self.market.get_klines(symbol, interval=config.TIMEFRAME)
                if not df.empty:
                    scan_candidates.append({'symbol': symbol, 'df': df})
            
            if not scan_candidates: return

            # Run analyses
            analysis_tasks = [
                loop.run_in_executor(self.executor, self.strategy.analyze, c['df']) 
                for c in scan_candidates
            ]
            results = await asyncio.gather(*analysis_tasks)
            
            # 3. Execution Logic
            for i, signal in enumerate(results):
                if signal and signal['score'] >= config.MIN_SCORE:
                    cand = scan_candidates[i]
                    # Execute
                    price = cand['df'].iloc[-1]['close']
                    move_pct = abs(config.STOP_LOSS_ROI / config.LEVERAGE / 100)
                    
                    sl, tp = 0, 0
                    if signal['direction'] == 'LONG':
                        sl = price * (1 - move_pct)
                        tp = price * (1 + (abs(config.TAKE_PROFIT_ROI) / config.LEVERAGE / 100))
                    else:
                        sl = price * (1 + move_pct)
                        tp = price * (1 - (abs(config.TAKE_PROFIT_ROI) / config.LEVERAGE / 100))
                        
                    amount = self.market.balance * (config.CAPITAL_PER_TRADE_PCT / 100)
                    if amount < 6.0: amount = 6.0 # Force min size
                    if amount > self.market.balance: continue # Skip if poor
                    await self.market.open_position(cand['symbol'], signal['direction'], amount, sl, tp)

        except Exception as e:
            logger.error(f"Scan Loop Error: {e}")

if __name__ == "__main__":
    import os
    dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
    api_key = os.getenv('API_KEY')
    api_secret = os.getenv('API_SECRET')
    
    bot = ScalpingBot(is_dry_run=dry_run, api_key=api_key, api_secret=api_secret)
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt: pass
