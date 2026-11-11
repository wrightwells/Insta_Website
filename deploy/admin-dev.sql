-- Disposable local login. Provision the named application owner separately.
CREATE ROLE admin_dev LOGIN PASSWORD 'admin-development-only';
GRANT site_admin TO admin_dev;
