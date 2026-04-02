# Deploy Trading Agent to Oracle Cloud (Free Forever)

## Runtime safety additions

- Use `deploy/sync_vm.sh` for normal repo -> VM releases.
- Every sync creates a manifest and a VM-side backup before replacing files.
- Backup retention is intentionally small by default (`BACKUP_RETENTION=5`) to avoid disk growth on small VMs.
- Emergency VM-only fixes must follow [`HOTFIX_ESCAPE_HATCH.md`](./HOTFIX_ESCAPE_HATCH.md).
- Post-sync verification can be run on the VM via `deploy/verify_vm.sh`.

## Step 1: Create Oracle Cloud Account (5 min)

1. Go to: **https://cloud.oracle.com/sign-up**
2. Fill in your details
3. **Credit card required for verification** (they do NOT charge you!)
4. Choose region: **US East (Ashburn)** or closest to US East Coast (less latency to Alpaca)
5. Wait for account activation (~2 minutes)

## Step 2: Create a Free VM (5 min)

1. Log in to Oracle Cloud Console
2. Click **"Create a VM instance"** (or go to Compute → Instances → Create)
3. Settings:
   - **Name:** `trading-agent`
   - **Image:** Ubuntu 22.04 (default is fine)
   - **Shape:** Click "Change Shape" → **Ampere** → **VM.Standard.A1.Flex**
     - OCPUs: **1**
     - Memory: **6 GB**
     - (This is within Always Free limits!)
   - **SSH Key:** Click "Generate a key pair" → **Download BOTH keys** (save them!)
4. Click **Create**
5. Wait ~1 minute until status shows **RUNNING**
6. Copy the **Public IP Address** (you'll need it)

## Step 3: Upload Project to VM (5 min)

Open Terminal on your Mac and run:

```bash
# Set your VM's IP address
VM_IP="YOUR_VM_IP_HERE"

# Upload the entire project
scp -i ~/Downloads/ssh-key-*.key -r ~/trading-agent ubuntu@$VM_IP:~/trading-agent

# Connect to the VM
ssh -i ~/Downloads/ssh-key-*.key ubuntu@$VM_IP
```

## Step 4: Setup on VM (3 min)

Once connected via SSH:

```bash
# Go to project
cd ~/trading-agent

# Create .env with your API keys
cp .env.example .env
nano .env
# Fill in: ALPACA_API_KEY, ALPACA_SECRET_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# Save: Ctrl+O, Enter, Ctrl+X

# Run the setup script (installs everything + creates auto-start)
chmod +x deploy/setup_oracle.sh
bash deploy/setup_oracle.sh
```

## Step 5: Start & Verify (2 min)

```bash
# Start the agent
sudo systemctl start trading-agent
sudo systemctl start trading-dashboard

# Check it's running
sudo systemctl status trading-agent

# Watch live logs
tail -f logs/agent.log
```

## Step 6: Open Dashboard Port (2 min)

To access the dashboard from your browser:

1. In Oracle Cloud Console → Networking → Virtual Cloud Networks
2. Click your VCN → Click the Subnet → Click Security List
3. Add **Ingress Rule:**
   - Source: `0.0.0.0/0`
   - Destination Port: `5555`
   - Description: `Trading Dashboard`
4. On the VM, also run:
   ```bash
   sudo iptables -I INPUT -p tcp --dport 5555 -j ACCEPT
   sudo netfilter-persistent save
   ```
5. Open in browser: `http://YOUR_VM_IP:5555`

## That's It!

The agent will automatically:
- Start every weekday at 09:25 ET (before market open)
- Stop every weekday at 16:05 ET (after market close)
- Run 24/7 on the cloud — no Mac needed!
- Restart if it crashes

## Useful Commands

```bash
# Connect to VM
ssh -i ~/Downloads/ssh-key-*.key ubuntu@YOUR_VM_IP

# Check agent status
sudo systemctl status trading-agent

# View live logs
tail -f ~/trading-agent/logs/agent.log

# Restart agent
sudo systemctl restart trading-agent

# Stop agent
sudo systemctl stop trading-agent

# Update code (from your Mac)
scp -i ~/Downloads/ssh-key-*.key -r ~/trading-agent ubuntu@YOUR_VM_IP:~/trading-agent
ssh -i ~/Downloads/ssh-key-*.key ubuntu@YOUR_VM_IP "cd ~/trading-agent && source venv/bin/activate && pip install -r requirements.txt && sudo systemctl restart trading-agent"
```
