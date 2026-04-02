#!/bin/bash
# ============================================================
# Oracle Cloud VM Setup Script
# Run this ONCE after SSH-ing into your new Oracle VM
# ============================================================

set -e

echo "╔════════════════════════════════════════╗"
echo "║   Trading Agent - Oracle Cloud Setup   ║"
echo "╚════════════════════════════════════════╝"
echo ""

# 1. Update system
echo "📦 Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Python 3.11+ and pip
echo "🐍 Installing Python..."
sudo apt-get install -y python3 python3-pip python3-venv git

# 3. Clone or create project directory
AGENT_DIR="$HOME/trading-agent"
if [ -d "$AGENT_DIR" ]; then
    echo "📁 Agent directory exists, updating..."
    cd "$AGENT_DIR"
else
    echo "📁 Creating agent directory..."
    mkdir -p "$AGENT_DIR"
    cd "$AGENT_DIR"
fi

# 4. Create virtual environment
echo "🔧 Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

# 5. Install dependencies
echo "📚 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 6. Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  IMPORTANT: Create your .env file!"
    echo "   cp .env.example .env"
    echo "   nano .env   # Fill in your API keys"
    echo ""
fi

# 7. Create directories
mkdir -p logs memory strategies_config

# 8. Setup systemd service (auto-start on boot)
echo "⚙️  Setting up systemd service..."
sudo tee /etc/systemd/system/trading-agent.service > /dev/null << 'SERVICEEOF'
[Unit]
Description=Autonomous Day Trading Agent
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/trading-agent
ExecStart=/home/ubuntu/trading-agent/venv/bin/python3 -m agent.main
Restart=on-failure
RestartSec=30
Environment=PYTHONUNBUFFERED=1

# Logging
StandardOutput=append:/home/ubuntu/trading-agent/logs/agent.log
StandardError=append:/home/ubuntu/trading-agent/logs/agent.log

[Install]
WantedBy=multi-user.target
SERVICEEOF

# 9. Setup dashboard service
sudo tee /etc/systemd/system/trading-dashboard.service > /dev/null << 'DASHEOF'
[Unit]
Description=Trading Agent Dashboard
After=network.target trading-agent.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/trading-agent
ExecStart=/home/ubuntu/trading-agent/venv/bin/python3 -m agent.dashboard --port 5555
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1

StandardOutput=append:/home/ubuntu/trading-agent/logs/dashboard.log
StandardError=append:/home/ubuntu/trading-agent/logs/dashboard.log

[Install]
WantedBy=multi-user.target
DASHEOF

# 10. Setup cron to start/stop agent during market hours
echo "⏰ Setting up market hours cron..."
# Create the scheduler script
tee "$AGENT_DIR/market_scheduler.sh" > /dev/null << 'CRONEOF'
#!/bin/bash
# Start agent at 09:25 ET (5 min before market open)
# Stop agent at 16:05 ET (5 min after market close)
# Run by cron

ACTION=$1
case $ACTION in
    start)
        echo "$(date): Starting trading agent..."
        sudo systemctl start trading-agent
        sudo systemctl start trading-dashboard
        ;;
    stop)
        echo "$(date): Stopping trading agent..."
        sudo systemctl stop trading-agent
        sudo systemctl stop trading-dashboard
        ;;
esac
CRONEOF
chmod +x "$AGENT_DIR/market_scheduler.sh"

# Add cron jobs (ET timezone = UTC-4 in summer, UTC-5 in winter)
# Using UTC times: 09:25 ET = 13:25 UTC (summer) / 14:25 UTC (winter)
# We'll use 13:25 UTC (covers summer, agent handles market-closed gracefully)
(crontab -l 2>/dev/null; echo "# Trading Agent - Start before market open (09:25 ET = 13:25 UTC)") | crontab -
(crontab -l 2>/dev/null; echo "25 13 * * 1-5 $AGENT_DIR/market_scheduler.sh start >> $AGENT_DIR/logs/scheduler.log 2>&1") | crontab -
(crontab -l 2>/dev/null; echo "# Trading Agent - Stop after market close (16:05 ET = 20:05 UTC)") | crontab -
(crontab -l 2>/dev/null; echo "5 20 * * 1-5 $AGENT_DIR/market_scheduler.sh stop >> $AGENT_DIR/logs/scheduler.log 2>&1") | crontab -

# 11. Enable services
sudo systemctl daemon-reload
sudo systemctl enable trading-agent
sudo systemctl enable trading-dashboard

echo ""
echo "✅ Setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Next steps:"
echo "  1. Edit .env: nano .env"
echo "  2. Test:      sudo systemctl start trading-agent"
echo "  3. Check:     sudo systemctl status trading-agent"
echo "  4. Logs:      tail -f logs/agent.log"
echo "  5. Dashboard: http://YOUR_VM_IP:5555"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🤖 The agent will auto-start every weekday at 09:25 ET"
echo "   and auto-stop at 16:05 ET."
echo ""
