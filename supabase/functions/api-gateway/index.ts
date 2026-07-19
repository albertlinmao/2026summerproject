import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import * as jose from "https://deno.land/x/jose@v4.14.4/index.ts";

const JWT_SECRET = Deno.env.get('SUPABASE_JWT_SECRET') || "";
const BACKEND_URL = Deno.env.get('K8S_FASTAPI_URL') || "http://host.docker.internal:8000"; 
const INTERNAL_SECRET = Deno.env.get('GATEWAY_PSK') || "default-dev-secret";
const SUPABASE_URL = Deno.env.get('SUPABASE_URL') || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') || "";

// Simple in-memory cache for tenant suspension check (as a substitute for Deno KV in local dev/Edge)
// In production, consider using a proper KV store if available
const tenantSuspensionCache = new Map<string, { suspended: boolean, timestamp: number }>();
const CACHE_TTL_MS = 60000; // 1 minute

// Simple Rate Limiting (Fixed Window per IP/Tenant)
const rateLimits = new Map<string, { count: number, resetAt: number }>();
const RATE_LIMIT_WINDOW_MS = 60000; // 1 minute
const MAX_REQUESTS_PER_WINDOW = 100;

function checkRateLimit(key: string): boolean {
  const now = Date.now();
  const record = rateLimits.get(key);

  if (!record || now > record.resetAt) {
    rateLimits.set(key, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return true;
  }

  if (record.count >= MAX_REQUESTS_PER_WINDOW) {
    return false;
  }

  record.count += 1;
  return true;
}

async function isTenantSuspended(tenantId: string): Promise<boolean> {
  const cached = tenantSuspensionCache.get(tenantId);
  if (cached && (Date.now() - cached.timestamp < CACHE_TTL_MS)) {
    return cached.suspended;
  }

  // Fallback to query Supabase directly
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/tenant?id=eq.${tenantId}&select=status`, {
      headers: {
        'apikey': SUPABASE_SERVICE_ROLE_KEY,
        'Authorization': `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`
      }
    });
    if (res.ok) {
      const data = await res.json();
      const suspended = data.length > 0 && data[0].status === 'SUSPENDED';
      tenantSuspensionCache.set(tenantId, { suspended, timestamp: Date.now() });
      return suspended;
    }
  } catch (err) {
    console.error("Error fetching tenant status:", err);
  }
  return false;
}

serve(async (req, connInfo) => {
  // CORS handling
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type' } })
  }

  // Rate Limiting by IP
  // Note: connInfo is available in std/http serve, but if not we fallback to header or default
  // In Supabase Edge Functions, client IP can often be found in x-forwarded-for
  const clientIp = req.headers.get('x-forwarded-for')?.split(',')[0] || 'unknown-ip';
  if (!checkRateLimit(clientIp)) {
    return new Response(JSON.stringify({ error: 'Too many requests' }), { status: 429, headers: { 'Content-Type': 'application/json' } });
  }

  const url = new URL(req.url);
  
  // Public route bypass for tenant registration
  if (url.pathname.match(/\/api\/v[0-9]+\/tenants\/?$/) && req.method === 'POST') {
     const backendReqUrl = `${BACKEND_URL}${url.pathname}${url.search}`;
     const headers = new Headers(req.headers);
     headers.set('X-Internal-Secret', INTERNAL_SECRET);
     // Generate Trace ID
     const traceId = crypto.randomUUID();
     headers.set('X-Trace-Id', traceId);

     const backendRes = await fetch(backendReqUrl, {
       method: req.method,
       headers: headers,
       body: req.body ? await req.blob() : undefined
     });
     return backendRes;
  }

  const authHeader = req.headers.get('Authorization');
  if (!authHeader) {
    return new Response(JSON.stringify({ error: 'Missing Authorization header' }), { status: 401 });
  }

  const token = authHeader.replace('Bearer ', '');

  try {
    const secret = new TextEncoder().encode(JWT_SECRET);
    const { payload } = await jose.jwtVerify(token, secret);
    
    const userId = payload.sub;
    const tenantId = payload.app_metadata?.tenant_id;

    if (!tenantId) {
      return new Response(JSON.stringify({ error: 'Tenant ID missing in token' }), { status: 403 });
    }

    // Check if tenant is suspended
    if (await isTenantSuspended(tenantId)) {
       return new Response(JSON.stringify({ error: 'Tenant is suspended' }), { status: 403 });
    }

    const backendReqUrl = `${BACKEND_URL}${url.pathname}${url.search}`;
    const headers = new Headers(req.headers);
    headers.set('X-User-Id', userId!);
    headers.set('X-Tenant-Id', tenantId);
    headers.set('X-Internal-Secret', INTERNAL_SECRET);
    
    // Generate Trace ID
    const traceId = crypto.randomUUID();
    headers.set('X-Trace-Id', traceId);

    const backendRes = await fetch(backendReqUrl, {
      method: req.method,
      headers: headers,
      body: req.body ? await req.blob() : undefined
    });

    return backendRes;
  } catch (error) {
    return new Response(JSON.stringify({ error: 'Invalid or expired token' }), { status: 401 });
  }
});
