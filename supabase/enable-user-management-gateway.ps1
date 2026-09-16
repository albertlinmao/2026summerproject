#!/usr/bin/env pwsh
#
# Enable the User Management API on the Supabase Gateway (Kong).
# PowerShell port of enable-user-management-gateway.sh.
#
# Conditions:
#   - Supabase is deployed with supabase/docker-compose.yml
#   - Docker Desktop is running
#   - The User Management backend container (api/user-management/backend)
#     is running on the same 'supabase_default' network
#
# Usage:
#   ./enable-user-management-gateway.ps1
#
# After running, the User Management API is reachable via Kong at:
#   http://localhost:8000/api/user-management/v1/
# with an {apikey} header using the anon or service_role key from supabase/.env.

$ErrorActionPreference = 'Stop'

$BACKEND_CONTAINER = "user-management-backend"
$KONG_CONTAINER    = "supabase-kong"
$ROUTE_PREFIX      = "/api/user-management/v1/"

$SCRIPT_DIR      = $PSScriptRoot
$PROJECT_ROOT    = Split-Path -Parent $SCRIPT_DIR
$ENV_FILE        = Join-Path $SCRIPT_DIR ".env"
$KONG_CONFIG     = Join-Path $SCRIPT_DIR "volumes\api\kong.yml"
$COMPOSE_FILE    = Join-Path $SCRIPT_DIR "docker-compose.yml"
$BACKEND_ENV     = Join-Path $PROJECT_ROOT "api\user-management\backend\.env"
$BACKEND_COMPOSE = Join-Path $PROJECT_ROOT "api\user-management\backend\docker-compose.yml"

function Get-EnvValue {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Key
    )
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match "^${Key}=") {
            return $line.Substring($line.IndexOf('=') + 1)
        }
    }
    return $null
}

$KONG_HTTP_PORT = Get-EnvValue -Path $ENV_FILE -Key "KONG_HTTP_PORT"
if (-not $KONG_HTTP_PORT) { $KONG_HTTP_PORT = "8000" }

Write-Host "===> Checking Docker is running..."
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not running. Start Docker Desktop first."
    exit 1
}

Write-Host "===> Checking Supabase network exists..."
docker network inspect supabase_default *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Supabase stack is not up. Start it with 'docker compose up' in $SCRIPT_DIR."
    exit 1
}

Write-Host "===> Checking User Management backend container..."
$backendNames = docker ps --filter "name=^/${BACKEND_CONTAINER}$" --filter "status=running" --format '{{.Names}}'
if ($backendNames -notmatch "^${BACKEND_CONTAINER}$") {
    Write-Host "WARNING: Container '$BACKEND_CONTAINER' is not running."
    Write-Host "Start it first with 'docker compose up' in api/user-management/backend, then re-run this script."
}

Write-Host "===> Recreating backend container to apply host port 28081 mapping..."
if (Test-Path -LiteralPath $BACKEND_COMPOSE) {
    docker compose -f $BACKEND_COMPOSE up -d --no-deps
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Failed to recreate backend container with $BACKEND_COMPOSE."
    } else {
        Write-Host "Backend container recreated with updated port mapping."
    }
} else {
    Write-Host "NOTE: $BACKEND_COMPOSE not found; skipping backend container recreation."
}

Write-Host "===> Ensuring GATEWAY_PSK is set in $ENV_FILE..."
if (-not (Test-Path -LiteralPath $ENV_FILE)) {
    Write-Host "ERROR: $ENV_FILE not found. Is Supabase configured?"
    exit 1
}

$GATEWAY_PSK = Get-EnvValue -Path $ENV_FILE -Key "GATEWAY_PSK"
if (-not $GATEWAY_PSK -and (Test-Path -LiteralPath $BACKEND_ENV)) {
    $BACKEND_PSK = Get-EnvValue -Path $BACKEND_ENV -Key "GATEWAY_PSK"
    if ($BACKEND_PSK) {
        Copy-Item -LiteralPath $ENV_FILE -Destination "$ENV_FILE.bak"
        Add-Content -LiteralPath $ENV_FILE -Value @(
            ""
            "# Shared secret used by Kong to authenticate upstream requests to the"
            "# User Management backend via the X-Internal-Secret header."
            "# Must match GATEWAY_PSK in api/user-management/backend/.env"
            "GATEWAY_PSK=$BACKEND_PSK"
        )
        $GATEWAY_PSK = $BACKEND_PSK
        Write-Host "Added GATEWAY_PSK to $ENV_FILE (backup saved to $ENV_FILE.bak)."
    }
}
if (-not $GATEWAY_PSK) {
    Write-Host "ERROR: GATEWAY_PSK is not set in $ENV_FILE and could not be read from $BACKEND_ENV."
    exit 1
}

Write-Host "===> Ensuring Kong receives GATEWAY_PSK from $COMPOSE_FILE..."
$composeBody = Get-Content -LiteralPath $COMPOSE_FILE -Raw
if ($composeBody -notmatch '(?m)^[ \t]*GATEWAY_PSK:') {
    if ($composeBody -match '(?m)^[ \t]*DASHBOARD_PASSWORD: ') {
        $nl = if ($composeBody.Contains("`r`n")) { "`r`n" } else { "`n" }
        $updated = [regex]::Replace(
            $composeBody,
            '(?m)^([ \t]*)DASHBOARD_PASSWORD: .*$',
            {
                param($m)
                $indent = $m.Groups[1].Value
                "${indent}DASHBOARD_PASSWORD: `${DASHBOARD_PASSWORD}${nl}${indent}GATEWAY_PSK: `${GATEWAY_PSK}"
            }
        )
        [System.IO.File]::WriteAllText($COMPOSE_FILE, $updated)
        Write-Host "Added GATEWAY_PSK to the Kong service environment in $COMPOSE_FILE."
    } else {
        Write-Host "ERROR: Could not locate Kong service environment in $COMPOSE_FILE to add GATEWAY_PSK."
        exit 1
    }
} else {
    Write-Host "GATEWAY_PSK already present in $COMPOSE_FILE."
}

Write-Host "===> Ensuring 'user-mgmt-v1' service entry exists in $KONG_CONFIG..."
if (-not (Test-Path -LiteralPath $KONG_CONFIG)) {
    Write-Host "ERROR: $KONG_CONFIG not found."
    exit 1
}
if ((Get-Content -LiteralPath $KONG_CONFIG -Raw) -notmatch 'user-mgmt-v1') {
    Copy-Item -LiteralPath $KONG_CONFIG -Destination "$KONG_CONFIG.bak"
    $userMgmtBlock = @'

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
'@
    Add-Content -LiteralPath $KONG_CONFIG -Value $userMgmtBlock
    Write-Host "Appended 'user-mgmt-v1' to $KONG_CONFIG (backup saved to $KONG_CONFIG.bak)."
} else {
    Write-Host "Route 'user-mgmt-v1' already present; checking upstream URL..."
    $kongRaw = Get-Content -LiteralPath $KONG_CONFIG -Raw
    if ($kongRaw -match '(?m)url: http://user-management-backend:8080/$') {
        Copy-Item -LiteralPath $KONG_CONFIG -Destination "$KONG_CONFIG.bak"
        $updated = $kongRaw -replace '(?m)url: http://user-management-backend:8080/$', 'url: http://user-management-backend:8080/api/v1/'
        $updated = $updated -replace '(?m)http://user-management-backend:8080/\*', 'http://user-management-backend:8080/api/v1/*'
        [System.IO.File]::WriteAllText($KONG_CONFIG, $updated)
        Write-Host "Fixed stale upstream URL for 'user-mgmt-v1' (backup saved to $KONG_CONFIG.bak)."
    } else {
        Write-Host "Upstream URL for 'user-mgmt-v1' is up to date."
    }
}

Write-Host "===> Recreating Kong to apply updated env and declarative config..."
docker compose -f $COMPOSE_FILE up -d --no-deps kong
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "===> Waiting for Kong to be ready..."
for ($i = 1; $i -le 30; $i++) {
    docker exec $KONG_CONTAINER kong health *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Kong is ready (after ${i}s)."
        break
    }
    if ($i -eq 30) {
        Write-Host "ERROR: Kong did not become ready within 30 seconds."
        Write-Host "Check Kong logs: docker logs $KONG_CONTAINER"
        exit 1
    }
    Start-Sleep -Seconds 1
}

$API_KEY = ""
if (Test-Path -LiteralPath $ENV_FILE) {
    $keyLine = Get-Content -LiteralPath $ENV_FILE |
        Where-Object { $_ -match '^(ANON_KEY|SERVICE_ROLE_KEY)=' } |
        Select-Object -First 1
    if ($keyLine) { $API_KEY = $keyLine.Substring($keyLine.IndexOf('=') + 1) }
}

Write-Host "===> Verifying route is registered in Kong..."
docker exec $KONG_CONTAINER sh -c "cat /home/kong/kong.yml | grep -q 'user-mgmt-v1'" *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Route 'user-mgmt-v1' found in Kong config."
} else {
    Write-Host "WARNING: Could not find 'user-mgmt-v1' inside Kong container config."
}

$smokeUrl = "http://localhost:${KONG_HTTP_PORT}${ROUTE_PREFIX}roles/"
Write-Host "===> Smoke-testing the route through Kong at $smokeUrl..."
if ($API_KEY) {
    $httpCode = & curl.exe -s -o NUL -w '%{http_code}' -H "apikey: $API_KEY" $smokeUrl
    Write-Host "HTTP status from backend: $httpCode"
    switch ($httpCode) {
        { $_ -in @("200", "400") } {
            Write-Host "PASS: Route reached the User Management backend."
            Write-Host "      (400 is expected here: roles routes require the X-Tenant-Id/X-User-Id identity"
            Write-Host "      headers that Kong does not inject. In production the Supabase Auth Edge"
            Write-Host "      gateway provides them; locally that is not present.)"
        }
        { $_ -in @("401", "403") } {
            Write-Host "NOTE: API gateway rejected the request (key-auth/ACL or GATEWAY_PSK mismatch)."
            Write-Host "Check the anon/service_role key and GATEWAY_PSK in $ENV_FILE."
        }
        "404" {
            Write-Host "ERROR: Route not found. Check that 'user-mgmt-v1' is registered in $KONG_CONFIG."
        }
        default {
            Write-Host "NOTE: Unexpected HTTP status '$httpCode'. Verify the backend is running and reachable from the Supabase network."
        }
    }
} else {
    Write-Host "NOTE: Skipped smoke test - no ANON_KEY/SERVICE_ROLE_KEY found in $ENV_FILE."
}

Write-Host ""
Write-Host "Done. User Management API is now exposed via Kong:"
Write-Host "  Base URL: http://localhost:${KONG_HTTP_PORT}${ROUTE_PREFIX}"
Write-Host "  Header:   apikey: <SUPABASE_ANON_KEY|SUPABASE_SERVICE_KEY>"
Write-Host ""
Write-Host "Direct access to the backend (bypassing Kong) uses host port 28081:"
Write-Host "  http://localhost:28081"