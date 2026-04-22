#!/bin/bash
set -e

echo ""
echo "  ADHED — headless task management for agents and claws."
echo ""

# Check Docker
if ! docker info >/dev/null 2>&1; then
    echo "  ❌ Docker is not running. Start Docker and try again."
    exit 1
fi

# Check if already set up
if [ -f .adhed-credentials ]; then
    echo "  ✅ ADHED is already set up."
    echo ""
    cat .adhed-credentials
    echo ""
    echo "  API docs: http://localhost:${API_PORT:-8100}/docs"
    exit 0
fi

# Prompt
read -p "  Your name: " USER_NAME
read -p "  Your email: " USER_EMAIL
read -p "  Team name [Home]: " TEAM_NAME
TEAM_NAME=${TEAM_NAME:-Home}
TEAM_KEY=$(echo "$TEAM_NAME" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z' | head -c 10)
read -p "  Team key [$TEAM_KEY]: " INPUT_KEY
TEAM_KEY=${INPUT_KEY:-$TEAM_KEY}

echo ""
echo "  Starting services..."

# Start
docker compose up -d 2>/dev/null

# Create test database if it doesn't exist (idempotent)
DB_CONTAINER=$(docker compose ps -q adhed-db 2>/dev/null)
if [ -n "$DB_CONTAINER" ]; then
    docker exec "$DB_CONTAINER" psql -U adhed -tc \
        "SELECT 1 FROM pg_database WHERE datname = 'adhed_test'" 2>/dev/null \
        | grep -q 1 \
        || docker exec "$DB_CONTAINER" psql -U adhed -c "CREATE DATABASE adhed_test;" 2>/dev/null
fi

# Wait for healthy
API_PORT=${API_PORT:-8100}
echo -n "  Waiting for API"
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${API_PORT}/api/v1/health" >/dev/null 2>&1; then
        echo " ✓"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo ""
        echo "  ❌ API failed to start. Check: docker compose logs adhed-api"
        exit 1
    fi
    echo -n "."
    sleep 2
done

# Setup
RESULT=$(curl -sf -X POST "http://localhost:${API_PORT}/api/v1/setup" \
    -H "Content-Type: application/json" \
    -d "{\"team_name\":\"$TEAM_NAME\",\"team_key\":\"$TEAM_KEY\",\"user_name\":\"$USER_NAME\",\"user_email\":\"$USER_EMAIL\"}" 2>&1)

if [ $? -ne 0 ]; then
    echo "  ❌ Setup failed. ADHED may already be configured."
    echo "     Check: curl http://localhost:${API_PORT}/api/v1/health"
    exit 1
fi

# Parse response
API_KEY=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])")
USER_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['user_id'])")
TEAM_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['team_id'])")

# Save credentials
cat > .adhed-credentials << EOF
API_KEY=$API_KEY
USER_ID=$USER_ID
TEAM_ID=$TEAM_ID
URL=http://localhost:${API_PORT}
EOF

echo ""
echo "  ✅ ADHED is running!"
echo ""
echo "  Team:    $TEAM_NAME ($TEAM_KEY)"
echo "  User:    $USER_NAME (owner)"
echo "  API Key: $API_KEY"
echo "  URL:     http://localhost:${API_PORT}"
echo "  Docs:    http://localhost:${API_PORT}/docs"
echo ""
echo "  Credentials saved to .adhed-credentials"
echo ""
