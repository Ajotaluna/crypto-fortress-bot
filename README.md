# 🏰 Crypto Fortress Bot (The "Brain")

**Automatic Regime Detection System** for Binance Futures.

This bot is designed to solve the "Market Context" problem. Instead of blindly following trends or scalping ranges, it first asks: **"What is the market doing?"**

## 🧠 Core Strategy: "Regime Detection"

The bot uses a central "Brain" (`fortress_main.py`) that analyzes BTC/Market conditions every 5 minutes:

| Market Regime | Detection Logic | Active Strategy | behavior |
|--------------|----------------|----------------|----------|
| **TRENDING** 🚀 | `ADX > 25` AND `Price > EMA200` | **Trend Bot** | Rides long swings (1h - 24h). Pyramids profits. |
| **RANGING** 🦀 | `ADX < 20` OR `Choppy Volume` | **Scalp Bot** | Quick reversions (mins). Buys Low / Sells High. |
| **DUMPING** 🩸 | `Price < EMA200` (1H) | **Protective** | Only Shorts allowed (or Cash is King). |

## 🛠️ Installation & Usage

### Option A: 1-Click AWS Deployment (Recommended)
Use the included script to auto-install Docker and run the bot on a fresh Ubuntu server.

```bash
# 1. Upload script to server
scp deploy_fortress.sh ubuntu@YOUR_IP:~/

# 2. Run it
chmod +x deploy_fortress.sh
./deploy_fortress.sh
```

### Option B: Manual Docker Run
If you already have Docker installed:

```bash
# Build
docker build -t fortress-bot .

# Run (Production Mode)
docker run -d --restart=always --name fortress-bot \
  -e API_KEY='YOUR_REAL_KEY' \
  -e API_SECRET='YOUR_REAL_SECRET' \
  fortress-bot python FortressBot/fortress_main.py
```

### Option C: Simulation / Testing
Want to test the logic without money? Use `DRY_RUN`:

```bash
docker run -d --name fortress-test \
  -e DRY_RUN='true' \
  -e API_KEY='x' -e API_SECRET='y' \
  fortress-bot python FortressBot/fortress_main.py
```

## ⚙️ Key Configuration (`config.py`)

- **`MAX_OPEN_POSITIONS`**: 10 (Default for stress testing).
- **`DAILY_PROFIT_TARGET_PCT`**: 3.0% (Bot keeps compounding, but reports this target).
- **`STOP_LOSS_PCT`**: 1.5% (Dynamic).
- **`MIN_VOLUME`**: 50M USDT (Filters junk coins).

## 🛡️ "The Fortress" Safety Features
1. **Circuit Breaker**: If Daily Loss > -1%, bot SLEEPS for 24h. No rage trading.
2. **Analysis Paralysis Fix**: Parallel processing for analyzing 50+ pairs instantly.
3. **Compound Interest**: Profits are automatically added to next trade size.

---
*Disclaimer: Use at your own risk. Crypto trading involves significant risk of loss.*
