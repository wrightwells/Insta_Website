-- Local disposable login only, applied after roles.sql and migrations.
CREATE ROLE public_dev LOGIN PASSWORD 'public-development-only';
GRANT site_public TO public_dev;
