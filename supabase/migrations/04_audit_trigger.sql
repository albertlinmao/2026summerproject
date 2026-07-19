-- Create the masking function for audit logs
CREATE OR REPLACE FUNCTION public.audit_masking_trigger() 
RETURNS TRIGGER AS $$
DECLARE
    old_record JSONB;
    new_record JSONB;
    pii_columns TEXT[] := ARRAY['email', 'first_name', 'middle_name', 'last_name'];
    col TEXT;
BEGIN
    -- Convert records to JSONB
    old_record := to_jsonb(OLD);
    new_record := to_jsonb(NEW);

    -- Loop through known PII columns and stub them out
    FOREACH col IN ARRAY pii_columns LOOP
        IF old_record ? col THEN
            old_record := jsonb_set(old_record, ARRAY[col], '"[REDACTED_PII]"'::jsonb);
        END IF;
        IF new_record ? col THEN
            new_record := jsonb_set(new_record, ARRAY[col], '"[REDACTED_PII]"'::jsonb);
        END IF;
    END LOOP;

    -- Determine user making the change. For requests coming from FastAPI (which uses service_role),
    -- we might need to rely on a custom claim or context. For now, we try to grab auth.uid() if it's available.
    -- Otherwise, it stays null (or we can inject it via session variables).

    -- Insert into audit log, extracting the UUID dynamically
    INSERT INTO public.audit_log (table_name, record_id, action, old_data, new_data, changed_by)
    VALUES (
        TG_TABLE_NAME, 
        COALESCE((new_record->>'id')::UUID, (old_record->>'id')::UUID), 
        TG_OP, 
        old_record, 
        new_record,
        auth.uid()
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Attach to core tables
CREATE TRIGGER audit_user_profile_trigger
AFTER INSERT OR UPDATE OR DELETE ON public.user_profile
FOR EACH ROW EXECUTE FUNCTION public.audit_masking_trigger();

CREATE TRIGGER audit_tenant_trigger
AFTER INSERT OR UPDATE OR DELETE ON public.tenant
FOR EACH ROW EXECUTE FUNCTION public.audit_masking_trigger();

CREATE TRIGGER audit_membership_trigger
AFTER INSERT OR UPDATE OR DELETE ON public.membership
FOR EACH ROW EXECUTE FUNCTION public.audit_masking_trigger();

CREATE TRIGGER audit_role_trigger
AFTER INSERT OR UPDATE OR DELETE ON public.role
FOR EACH ROW EXECUTE FUNCTION public.audit_masking_trigger();
