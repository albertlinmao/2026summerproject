#!/bin/bash
#
# Enable the User Management API on the Supabase Gateway (Kong).
#
# Conditions:
#   - Supabase is deployed with supabase/docker-compose.yml
#   - Docker Desktop is running
#   - The User Management backend container (api/user-management/backend)
#     is running on the same 'supabase_default' network
#
# Usage:
#   ./enable-user-management-gateway.sh
#
# What it does (idempotent):
#   1. Ensures supabase/.env defines GATEWAY_PSK (synced from the backend .env).
#   2. Ensures supabase/docker-compose.yml passes GATEWAY_PSK into Kong.
#   3. Ensures the 'user-mgmt-v1' service entry exists in volumes/api/kong.yml.
#   4. Recreates the backend container to apply the host port 28081 mapping.
#   5. Recreates/restarts the Kong container to apply the new config.
#   6. Verifies the route is registered and smoke-tests it through Kong.
#
# After running, the User Management API is reachable via Kong at:
#   http://localhost:8000/api/user-management/v1/
# with an {apikey} header using the anon or service_role key from supabase/.env.

set -euo pipefail

BACKEND_CONTAINER="user-management-backend"
KONG_CONTAINER="supabase-kong"
ROUTE_PREFIX="/api/user-management/v1/"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$SCRIPT_DIR/.env"
KONG_CONFIG="$SCRIPT_DIR/volumes/api/kong.yml"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
BACKEND_ENV="$PROJECT_ROOT/api/user-management/backend/.env"

KONG_HTTP_PORT="$(sed -n 's/^KONG_HTTP_PORT=//p' "$ENV_FILE" 2>/dev/null | head -n1)"
KONG_HTTP_PORT="${KONG_HTTP_PORT:-8000}"

echo "===> Checking Docker is running..."
docker info >/dev/null 2>&1 || {
  echo "ERROR: Docker is not running. Start Docker Desktop first."
  exit 1
}

echo "===> Checking Supabase network exists..."
if ! docker network inspect supabase_default >/dev/null 2>&1; then
  echo "ERROR: Supabase stack is not up. Start it with 'docker compose up' in $SCRIPT_DIR."
  exit 1
fi

echo "===> Checking User Management backend container..."
if ! docker ps --filter "name=^/${BACKEND_CONTAINER}$" --filter "status=running" --format '{{.Names}}' | grep -q "^${BACKEND_CONTAINER}$"; then
  echo "WARNING: Container '$BACKEND_CONTAINER' is not running."
  echo "Start it first with 'docker compose up' in api/user-management/backend, then re-run this script."
fi

BACKEND_COMPOSE="$PROJECT_ROOT/api/user-management/backend/docker-compose.yml"
echo "===> Recreating backend container to apply host port 28081 mapping..."
if [ -f "$BACKEND_COMPOSE" ]; then
  if docker compose -f "$BACKEND_COMPOSE" up -d --no-deps; then
    echo "Backend container recreated with updated port mapping."
  else
    echo "WARNING: Failed to recreate backend container with $BACKEND_COMPOSE."
  fi
else
  echo "NOTE: $BACKEND_COMPOSE not found; skipping backend container recreation."
fi

echo "===> Ensuring GATEWAY_PSK is set in $ENV_FILE..."
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Is Supabase configured?"
  exit 1
fi

GATEWAY_PSK="$(sed -n 's/^GATEWAY_PSK=//p' "$ENV_FILE" | head -n1)"
if [ -z "$GATEWAY_PSK" ] && [ -f "$BACKEND_ENV" ]; then
  BACKEND_PSK="$(sed -n 's/^GATEWAY_PSK=//p' "$BACKEND_ENV" | head -n1)"
  if [ -n "$BACKEND_PSK" ]; then
    cp "$ENV_FILE" "$ENV_FILE.bak"
    printf '\n# Shared secret used by Kong to authenticate upstream requests to the\n# User Management backend via the X-Internal-Secret header.\n# Must match GATEWAY_PSK in api/user-management/backend/.env\nGATEWAY_PSK=%s\n' "$BACKEND_PSK" >> "$ENV_FILE"
    GATEWAY_PSK="$BACKEND_PSK"
    echo "Added GATEWAY_PSK=$BACKEND_PSK (backup saved to $ENV_FILE.bak)."
  fi
fi
if [ -z "$GATEWAY_PSK" ]; then
  echo "ERROR: GATEWAY_PSK is not set in $ENV_FILE and could not be read from $BACKEND_ENV."
  exit 1
fi

echo "===> Ensuring Kong receives GATEWAY_PSK from $COMPOSE_FILE..."
if ! grep -q '^[[:space:]]*GATEWAY_PSK:' "$COMPOSE_FILE"; then
  if grep -q 'DASHBOARD_PASSWORD: ' "$COMPOSE_FILE"; then
    sed -i 's/^\([[:space:]]*\)DASHBOARD_PASSWORD: .*/\1DASHBOARD_PASSWORD: ${DASHBOARD_PASSWORD}\n\1GATEWAY_PSK: ${GATEWAY_PSK}/' "$COMPOSE_FILE"
    echo "Added GATEWAY_PSK to the Kong service environment in $COMPOSE_FILE."
  else
    echo "ERROR: Could not locate Kong service environment in $COMPOSE_FILE to add GATEWAY_PSK."
    exit 1
  fi
else
  echo "GATEWAY_PSK already present in $COMPOSE_FILE."
fi

echo "===> Ensuring 'user-mgmt-v1' service entry exists in $KONG_CONFIG..."
if [ ! -f "$KONG_CONFIG" ]; then
  echo "ERROR: $KONG_CONFIG not found."
  exit 1
fi

if ! grep -q 'user-mgmt-v1' "$KONG_CONFIG"; then
  cp "$KONG_CONFIG" "$KONG_CONFIG.bak"
  cat >> "$KONG_CONFIG" <<'EOF'

  ## Secure User Management routes
  - name: user-mgmt-v1
    _comment: 'User Management: /api/user-management/v1/* -> http://user-management-backend:8080/api/v1/*'
    url: http://user-management-backend:8080/api/v1/
    routes:
      - name: user-mgmt-v1-all
        strip_path: true
        paths:
          - /api/user-management/v1/
    plugins:
      - name: cors
      - name: key-auth
        config:
          hide_credentials: true
      - name: acl
        config:
          hide_groups_header: true
          allow:
            - admin
            - anon
      - name: request-transformer
        config:
          add:
            headers:
              - X-Internal-Secret:$GATEWAY_PSK
EOF
  echo "Appended 'user-mgmt-v1' to $KONG_CONFIG (backup saved to $KONG_CONFIG.bak)."
else
  echo "Route 'user-mgmt-v1' already present; checking upstream URL..."
  if grep -q 'url: http://user-management-backend:8080/$' "$KONG_CONFIG"; then
    cp "$KONG_CONFIG" "$KONG_CONFIG.bak"
    sed -i 's|url: http://user-management-backend:8080/$|url: http://user-management-backend:8080/api/v1/|' "$KONG_CONFIG"
    sed -i 's|http://user-management-backend:8080/\*|http://user-management-backend:8080/api/v1/*|' "$KONG_CONFIG"
    echo "Fixed stale upstream URL for 'user-mgmt-v1' (backup saved to $KONG_CONFIG.bak)."
  else
    echo "Upstream URL for 'user-mgmt-v1' is up to date."
  fi
fi

echo "===> Recreating Kong to apply updated env and declarative config..."
docker compose -f "$COMPOSE_FILE" up -d --no-deps kong

echo "===> Waiting for Kong to be ready..."
for i in $(seq 1 30); do
  if docker exec "$KONG_CONTAINER" kong health >/dev/null 2>&1; then
    echo "Kong is ready (after ${i}s)."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: Kong did not become ready within 30 seconds."
    echo "Check Kong logs: docker logs $KONG_CONTAINER"
    exit 1
  fi
  sleep 1
done

# Extract the anon/service key from supabase/.env if present for the smoke test.
API_KEY=""
if [ -f "$ENV_FILE" ]; then
  API_KEY="$(grep -E '^(ANON_KEY|SERVICE_ROLE_KEY)=' "$ENV_FILE" | head -n1 | cut -d= -f2-)"
fi

echo "===> Verifying route is registered in Kong..."
if docker exec "$KONG_CONTAINER" sh -c "cat /home/kong/kong.yml | grep -q 'user-mgmt-v1'"; then
  echo "Route 'user-mgmt-v1' found in Kong config."
else
  echo "WARNING: Could not find 'user-mgmt-v1' inside Kong container config."
fi

echo "===> Smoke-testing the route through Kong at http://localhost:${KONG_HTTP_PORT}${ROUTE_PREFIX}roles/..."
if [ -n "$API_KEY" ]; then
  http_code="$(curl -s -o /dev/null -w '%{http_code}' -H "apikey: $API_KEY" \
    "http://localhost:${KONG_HTTP_PORT}${ROUTE_PREFIX}roles/" || true)"
  echo "HTTP status from backend: $http_code"
  case "$http_code" in
    200|400)
      echo "PASS: Route reached the User Management backend."
      echo "      (400 is expected here: roles routes require the X-Tenant-Id/X-User-Id identity"
      echo "      headers that Kong does not inject. In production the Supabase Auth Edge"
      echo "      gateway provides them; locally that is not present.)"
      ;;
    401|403)
      echo "NOTE: API gateway rejected the request (key-auth/ACL or GATEWAY_PSK mismatch)."
      echo "Check the anon/service_role key and GATEWAY_PSK in $ENV_FILE."
      ;;
    404)
      echo "ERROR: Route not found. Check that 'user-mgmt-v1' is registered in $KONG_CONFIG."
      ;;
    *)
      echo "NOTE: Unexpected HTTP status '$http_code'. Verify the backend is running and reachable from the Supabase network."
      ;;
  esac
else
  echo "NOTE: Skipped smoke test - no ANON_KEY/SERVICE_ROLE_KEY found in $ENV_FILE."
fi

echo ""
echo "Done. User Management API is now exposed via Kong:"
echo "  Base URL: http://localhost:${KONG_HTTP_PORT}${ROUTE_PREFIX}"
echo "  Header:   apikey: <SUPABASE_ANON_KEY|SUPABASE_SERVICE_KEY>"
echo ""
echo "Direct access to the backend (bypassing Kong) uses host port 28081:"
echo "  http://localhost:28081"