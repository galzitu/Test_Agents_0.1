# Restart Trading Agent Server

## Description
Restart the autonomous day trading agent. Gracefully stops the running process and starts it again, with health verification.

## Trigger
User says: "restart server", "restart trading agent", "restart the agent", "reboot agent", or uses `/restart-server`

## Instructions

Follow these steps in order:

### Step 1: Find the running process
```bash
ps aux | grep '[p]ython3 -m agent.main' | head -5
```
Also check for start.sh:
```bash
ps aux | grep '[s]tart.sh' | head -5
```
Save the PIDs.

### Step 2: Stop gracefully
If a process is found, send SIGTERM (graceful shutdown) to the Python process:
```bash
kill <PID>
```
Wait up to 10 seconds for it to exit:
```bash
for i in $(seq 1 10); do
  if ! kill -0 <PID> 2>/dev/null; then
    echo "Process stopped cleanly"
    break
  fi
  sleep 1
done
```
If it's still running after 10 seconds, force kill:
```bash
kill -9 <PID> 2>/dev/null
```

If NO process is found, report "No running trading agent found" and proceed to start.

### Step 3: Start the agent
```bash
cd /Users/galzituni/trading-agent && source venv/bin/activate && nohup python3 -m agent.main > /dev/null 2>&1 &
echo "Started with PID: $!"
```

### Step 4: Health check
Wait 3 seconds, then verify:
```bash
sleep 3 && ps aux | grep '[p]ython3 -m agent.main' | head -3
```
If the process is running, report success. If not, check the latest log:
```bash
tail -20 /Users/galzituni/trading-agent/logs/agent_$(date +%Y-%m-%d).log
```
Report the error to the user.

### Step 5: Report
Tell the user:
- Whether a previous process was found and stopped
- The new PID
- Whether the health check passed
- If it's within market hours (ET 09:30-16:00) or outside them

## Important
- The project directory is `/Users/galzituni/trading-agent`
- Always activate the venv before running: `source venv/bin/activate`
- The main process is `python3 -m agent.main`
- Logs are in `/Users/galzituni/trading-agent/logs/`
- Never run without the `.env` file present
