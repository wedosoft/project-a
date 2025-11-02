-- Migration: Create set_config function for RLS tenant isolation
-- Created: 2025-11-02
-- Purpose: Enable tenant_id context setting for Row Level Security

CREATE OR REPLACE FUNCTION public.set_config(
    key text,
    value text
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Set configuration parameter for current transaction
    -- false = session-local setting (not persistent)
    PERFORM set_config(key, value, false);
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION public.set_config(text, text) TO authenticated;

-- Comment for documentation
COMMENT ON FUNCTION public.set_config(text, text) IS
'Sets a configuration parameter for the current transaction. Used for RLS tenant isolation.';
