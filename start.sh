#!/bin/bash
# ============================================================
# Trading Agent - Launch Script
# ============================================================
# Usage:
#   ./start.sh          - Run the trading agent
#   ./start.sh dashboard - Open the monitoring dashboard
#   ./start.sh status   - Show current status
#   ./start.sh test     - Test Alpaca connection
#   ./start.sh install  - Install dependencies
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

case "${1:-run}" in
    install)
        echo -e "${YELLOW}Installing dependencies...${NC}"

        # Check Python version
        if ! command -v python3 &> /dev/null; then
            echo -e "${RED}Python 3 not found! Install it first.${NC}"
            exit 1
        fi

        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        echo "Python version: $PYTHON_VERSION"

        # Create virtual environment if it doesn't exist
        if [ ! -d "venv" ]; then
            echo "Creating virtual environment..."
            python3 -m venv venv
        fi

        # Activate venv
        source venv/bin/activate

        # Install dependencies
        pip install -r requirements.txt

        echo -e "${GREEN}Dependencies installed!${NC}"
        echo ""
        echo "Next steps:"
        echo "  1. Copy .env.example to .env and fill in your API keys"
        echo "  2. Run: ./start.sh test"
        echo "  3. Run: ./start.sh"
        ;;

    test)
        echo -e "${YELLOW}Testing Alpaca connection...${NC}"

        if [ -d "venv" ]; then
            source venv/bin/activate
        fi

        python3 -m agent.main --test
        ;;

    status)
        echo -e "${YELLOW}Getting agent status...${NC}"

        if [ -d "venv" ]; then
            source venv/bin/activate
        fi

        python3 -m agent.main --status
        ;;

    dashboard|dash)
        echo -e "${YELLOW}Starting Dashboard...${NC}"

        if [ -d "venv" ]; then
            source venv/bin/activate
        fi

        python3 -m agent.dashboard --port "${2:-5555}"
        ;;

    run|"")
        echo -e "${GREEN}"
        echo "╔════════════════════════════════════════╗"
        echo "║     AUTONOMOUS DAY TRADING AGENT       ║"
        echo "║         Paper Trading Mode              ║"
        echo "╚════════════════════════════════════════╝"
        echo -e "${NC}"

        # Check .env exists
        if [ ! -f ".env" ]; then
            echo -e "${RED}Error: .env file not found!${NC}"
            echo "Copy .env.example to .env and fill in your API keys."
            exit 1
        fi

        if [ -d "venv" ]; then
            source venv/bin/activate
        fi

        # Save PID for watchdog
        python3 -m agent.main &
        AGENT_PID=$!
        echo "$AGENT_PID" > "$SCRIPT_DIR/logs/agent.pid"
        echo -e "${GREEN}Agent started with PID $AGENT_PID${NC}"
        echo "Watchdog PID file: logs/agent.pid"
        wait $AGENT_PID
        ;;

    *)
        echo "Usage: ./start.sh [install|test|status|dashboard|run]"
        echo ""
        echo "  install    - Install Python dependencies"
        echo "  test       - Test Alpaca connection"
        echo "  status     - Show current status"
        echo "  dashboard  - Start web dashboard (port 5555)"
        echo "  run        - Run the trading agent (default)"
        ;;
esac
