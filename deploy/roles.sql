-- Run once as the database operator before migrations. These groups have no
-- passwords and cannot log in. Provision per-environment login roles separately.
CREATE ROLE site_public NOLOGIN;
CREATE ROLE site_admin NOLOGIN;
CREATE ROLE site_agent NOLOGIN;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
-- Migrations grant only audited editorial/auth privileges to site_admin.
-- Agent grants remain absent until the importer contract is implemented.
