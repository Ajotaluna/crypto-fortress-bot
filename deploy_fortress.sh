#!/bin/bash

# Auto-Deploy Script for FortressBot (The Brain)
# 1. Installs Docker
# 2. Builds the FortressBot Image
# 3. Runs the Bot

# Update & Install Docker
sudo apt-get update
sudo apt-get install -y docker.io git python3-pip
sudo systemctl start docker
sudo systemctl enable docker

# Stop Old Bots (Clean Slate)
echo "Stopping old bots if running..."
sudo docker stop fortress-bot || true
sudo docker rm fortress-bot || true

# Build Docker Image
echo ">>> Building FortressBot Docker Image (Hybrid Titan)..."
sudo docker build -t fortress-bot .

echo "=========================================="
echo ">>> FORTRESS BOT UPDATED! 🚀"
echo "=========================================="
echo "To START the bot (with REAL MONEY), run this command:"
echo ""
echo "sudo docker run -d --restart=always --name fortress-bot \\"
echo "  -e API_KEY='YOUR_REAL_API_KEY' \\"
echo "  -e API_SECRET='YOUR_REAL_API_SECRET' \\"
echo "  -e DRY_RUN='false' \\"
echo "  fortress-bot python -u run_fortress_bot.py"
echo ""
echo "To VIEW LOGS:"
echo "sudo docker logs -f fortress-bot"
