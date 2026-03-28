#!/bin/bash
# ============================================================
# Deploy Trading Agent to Oracle Cloud VM
# Run this from your Mac AFTER creating the VM
# Usage: bash deploy/deploy_to_oracle.sh YOUR_VM_IP
# ============================================================

set -e

VM_IP="${1:-}"
SSH_KEY=$(ls ~/Downloads/ssh-key-*.key 2>/dev/null | head -1)

# ── Validate ────────────────────────────────────────────────
if [ -z "$VM_IP" ]; then
    echo "❌ Usage: bash deploy/deploy_to_oracle.sh YOUR_VM_IP"
    echo "   Example: bash deploy/deploy_to_oracle.sh 130.61.45.12"
    exit 1
fi

if [ -z "$SSH_KEY" ]; then
    echo "❌ SSH key not found in ~/Downloads/"
    echo "   Make sure you downloaded the key when creating the VM."
    exit 1
fi

echo "╔════════════════════════════════════════╗"
echo "║   Deploying Trading Agent to Oracle    ║"
echo "╚════════════════════════════════════════╝"
echo "  VM IP:   $VM_IP"
echo "  SSH Key: $SSH_KEY"
echo ""

# Fix SSH key permissions
chmod 600 "$SSH_KEY"

# ── Wait for VM to be reachable ──────────────────────────────
echo "⏳ Checking VM connection..."
for i in {1..10}; do
    if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=5 ubuntu@"$VM_IP" "echo ok" &>/dev/null; then
        echo "✅ VM is reachable!"
        break
    fi
    echo "   Attempt $i/10 — waiting 10 seconds..."
    sleep 10
done

# ── Upload project (excluding venv, logs, db, .env) ─────────
echo ""
echo "📤 Uploading project files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

rsync -avz --progress \
    --exclude='.env' \
    --exclude='venv/' \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='logs/*.log' \
    --exclude='memory/trading.db' \
    --exclude='.DS_Store' \
    --exclude='*.command' \
    --exclude='*.plist' \
    -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
    "$PROJECT_DIR/" \
    ubuntu@"$VM_IP":~/trading-agent/

echo ""
echo "✅ Files uploaded!"

# ── Run setup script on VM ───────────────────────────────────
echo ""
echo "⚙️  Running setup script on VM..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ubuntu@"$VM_IP" \
    "chmod +x ~/trading-agent/deploy/setup_oracle.sh && bash ~/trading-agent/deploy/setup_oracle.sh"

# ── Open firewall ports on VM ────────────────────────────────
echo ""
echo "🔥 Opening firewall port 5555..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ubuntu@"$VM_IP" "
    sudo iptables -I INPUT -p tcp --dport 5555 -j ACCEPT
    sudo apt-get install -y iptables-persistent -qq
    sudo netfilter-persistent save
"

# ── Print next steps ─────────────────────────────────────────
echo ""
echo "╔════════════════════════════════════════╗"
echo "║   ✅ Deployment Complete!              ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "📋 FINAL STEP — Set your API keys on the VM:"
echo ""
echo "   ssh -i $SSH_KEY ubuntu@$VM_IP"
echo "   nano ~/trading-agent/.env"
echo ""
echo "   Fill in:"
echo "     ALPACA_API_KEY=..."
echo "     ALPACA_SECRET_KEY=..."
echo "     TELEGRAM_BOT_TOKEN=..."
echo "     TELEGRAM_CHAT_ID=1766412347"
echo ""
echo "   Then start:"
echo "     sudo systemctl start trading-agent"
echo "     sudo systemctl start trading-dashboard"
echo ""
echo "📊 Dashboard will be at: http://$VM_IP:5555"
echo ""
echo "   ⚠️  Remember: also open port 5555 in Oracle Console:"
echo "   Networking → VCN → Security Lists → Add Ingress Rule → TCP 5555"
echo ""
