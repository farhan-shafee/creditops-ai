CREATE EXTENSION IF NOT EXISTS vector;
-- This role cannot write telemetry. Database owner credentials remain API-only.
CREATE ROLE creditops_diagnostics NOLOGIN;
GRANT CONNECT ON DATABASE creditops TO creditops_diagnostics;
GRANT USAGE ON SCHEMA public TO creditops_diagnostics;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO creditops_diagnostics;
ALTER DEFAULT PRIVILEGES FOR ROLE creditops IN SCHEMA public GRANT SELECT ON TABLES TO creditops_diagnostics;
ALTER ROLE creditops_diagnostics SET default_transaction_read_only = on;
