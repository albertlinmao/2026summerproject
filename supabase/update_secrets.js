const fs = require('fs');
const crypto = require('crypto');
const path = require('path');

const envPath = path.join(__dirname, '.env');

function generateSecret(length = 32) {
    return crypto.randomBytes(length).toString('hex');
}

function generatePassword(length = 16) {
    return crypto.randomBytes(length).toString('hex'); // Simple hex password
}

function base64Url(str) {
    return Buffer.from(str).toString('base64')
        .replace(/=/g, '')
        .replace(/\+/g, '-')
        .replace(/\//g, '_');
}

function sign(input, key) {
    const hmac = crypto.createHmac('sha256', key);
    hmac.update(input);
    return base64Url(hmac.digest());
}

function generateJwt(payload, secret) {
    const header = { alg: 'HS256', typ: 'JWT' };
    const headerEncoded = base64Url(JSON.stringify(header));
    const payloadEncoded = base64Url(JSON.stringify(payload));
    const signature = sign(`${headerEncoded}.${payloadEncoded}`, secret);
    return `${headerEncoded}.${payloadEncoded}.${signature}`;
}

const jwtSecret = generateSecret(40); // Ensure at least 32 chars
const postgresPassword = generatePassword(20);
const dashboardPassword = generatePassword(20);
const secretKeyBase = generateSecret(64);
const vaultEncKey = generateSecret(32);
const pgMetaCryptoKey = generateSecret(32);
const logflarePublic = generateSecret(32);
const logflarePrivate = generateSecret(32);

// JWT Payloads from original .env or standard Supabase defaults
/*
ANON_KEY payload:
{
    "role": "anon",
    "iss": "supabase-demo",
    "iat": 1641769200,
    "exp": 1799535600
}
SERVICE_ROLE_KEY payload:
{
    "role": "service_role",
    "iss": "supabase-demo",
    "iat": 1641769200,
    "exp": 1799535600
}
*/
// Set exp to 10 years from now approximately
const currentTimestamp = Math.floor(Date.now() / 1000);
const expTimestamp = currentTimestamp + (10 * 365 * 24 * 60 * 60);

const anonPayload = {
    role: 'anon',
    iss: 'supabase-demo',
    iat: currentTimestamp,
    exp: expTimestamp
};

const servicePayload = {
    role: 'service_role',
    iss: 'supabase-demo',
    iat: currentTimestamp,
    exp: expTimestamp
};

const anonKey = generateJwt(anonPayload, jwtSecret);
const serviceRoleKey = generateJwt(servicePayload, jwtSecret);

let envContent = fs.readFileSync(envPath, 'utf8');

// Replace using regex to ensure we catch the keys
envContent = envContent.replace(/^POSTGRES_PASSWORD=.*/m, `POSTGRES_PASSWORD=${postgresPassword}`);
envContent = envContent.replace(/^JWT_SECRET=.*/m, `JWT_SECRET=${jwtSecret}`);
envContent = envContent.replace(/^ANON_KEY=.*/m, `ANON_KEY=${anonKey}`);
envContent = envContent.replace(/^SERVICE_ROLE_KEY=.*/m, `SERVICE_ROLE_KEY=${serviceRoleKey}`);
envContent = envContent.replace(/^DASHBOARD_PASSWORD=.*/m, `DASHBOARD_PASSWORD=${dashboardPassword}`);
envContent = envContent.replace(/^SECRET_KEY_BASE=.*/m, `SECRET_KEY_BASE=${secretKeyBase}`);
envContent = envContent.replace(/^VAULT_ENC_KEY=.*/m, `VAULT_ENC_KEY=${vaultEncKey}`);
envContent = envContent.replace(/^PG_META_CRYPTO_KEY=.*/m, `PG_META_CRYPTO_KEY=${pgMetaCryptoKey}`);
envContent = envContent.replace(/^LOGFLARE_PUBLIC_ACCESS_TOKEN=.*/m, `LOGFLARE_PUBLIC_ACCESS_TOKEN=${logflarePublic}`);
envContent = envContent.replace(/^LOGFLARE_PRIVATE_ACCESS_TOKEN=.*/m, `LOGFLARE_PRIVATE_ACCESS_TOKEN=${logflarePrivate}`);

fs.writeFileSync(envPath, envContent);

console.log('Secrets replaced successfully in .env');
