import asyncio
import os
import sys
import logging
from config import config

# Ensure we can import from local directories
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import Fortress Bot
# Inside Docker /app, this is a direct import
from fortress_main import FortressBot

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("fortress_bot.log")
    ]
)
logger = logging.getLogger("Launcher")

async def main():
    logger.info("🚀 LAUNCHING FORTRESS BOT (Hybrid Protocol)...")
    
    # Initialize Configuration from Environment
    is_test_mode = os.getenv('DRY_RUN', 'true').lower() == 'true'
    config.DRY_RUN = is_test_mode # Inject into config
    
    logger.info("---------------------------------------------")
    logger.info(f"Mode: {'DRY RUN' if config.DRY_RUN else 'REAL MONEY'}")
    logger.info(f"Leverage: {config.LEVERAGE}x")
    logger.info(f"Symbol: SCANNER MODE (Top Pairs)")
    logger.info("---------------------------------------------")
    
    # Initialize Bot
    # Keys are loaded from Environment or Config
    bot = FortressBot(
        is_dry_run=config.DRY_RUN,
        api_key=os.getenv('API_KEY'),
        api_secret=os.getenv('API_SECRET')
    )
    
    # Start
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Fatal Error: {e}")
