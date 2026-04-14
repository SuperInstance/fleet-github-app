#!/bin/bash
# Fleet GitHub App — start webhook handler
source ~/.bashrc
export FLEET_WEBHOOK_SECRET="${FLEET_WEBHOOK_SECRET:-dev-secret}"
export FLEET_APP_PORT="${FLEET_APP_PORT:-8910}"
export GITHUB_TOKEN=$(grep GITHUB_TOKEN ~/.bashrc | head -1 | sed 's/.*=//' | tr -d "'" | tr -d '"')

echo "🔮 Starting Fleet GitHub App on :$FLEET_APP_PORT"
cd "$(dirname "$0")"
python3 webhook_handler.py &
PID=$!
echo "PID: $PID"
echo $PID > /tmp/fleet-app.pid
echo "Listening for webhooks..."
wait $PID
