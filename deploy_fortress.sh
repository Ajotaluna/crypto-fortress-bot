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

# Build Docker Image
echo "Building FortressBot Docker Image..."
sudo docker build -t fortress-bot .

# Stop Old Bots (Clean Slate)
echo "Stopping old bots if running..."
sudo docker stop fortress-bot || true
sudo docker rm fortress-bot || true

echo "
=========================================================
       FORTRESS BOT DEPLOYED SUCCESSFULLY! 🚀
=========================================================

To START the bot (PRODUCTION MODE), run this command:

sudo docker run -d --restart=always --name fortress-bot \\
  -e API_KEY='YOUR_REAL_API_KEY' \\
  -e API_SECRET='YOUR_REAL_API_SECRET' \\
  fortress-bot python -u FortressBot/fortress_main.py

To VIEW LOGS:
sudo docker logs -f fortress-bot
"
