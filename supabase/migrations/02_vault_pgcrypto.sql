-- Enable pgcrypto extension for PII encryption
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Ensure vault extension is enabled
CREATE EXTENSION IF NOT EXISTS supabase_vault CASCADE;

-- Insert a default encryption key for PII into Vault (in production this should be managed securely)
SELECT vault.create_secret(
    'super-secret-pii-encryption-key', -- the secret value
    'pii_encryption_key', -- the secret name
    'Key used for encrypting PII data like email and names in the user_profile table' -- description
);
