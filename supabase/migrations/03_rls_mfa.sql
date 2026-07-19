-- Enable Row Level Security on core tables
ALTER TABLE public.tenant ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.role ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.permission ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.role_permission ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.membership ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

-- Note: The FastAPI backend accesses the database using the SERVICE_ROLE_KEY,
-- which inherently bypasses RLS. The RLS policies below are primarily defense-in-depth
-- to ensure that even if a client attempts direct DB access, MFA (AAL2) is enforced
-- for elevated roles (if applicable) and tenant isolation is strictly checked.

-- Policy: Restrict data access to only users with AAL2 (MFA)
-- This is a baseline policy structure; in practice, you might scope this specifically
-- to administrative actions or specific tables.

-- Example MFA Policy for User Profile updates
CREATE POLICY "Require MFA for User Profile updates"
ON public.user_profile
FOR UPDATE
TO authenticated
USING (
    (select auth.jwt() ->> 'aal') = 'aal2'
);
