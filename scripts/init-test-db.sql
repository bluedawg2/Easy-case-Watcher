-- Create the test database for the brm project.
-- This script is executed once when the Postgres container is first created
-- (mounted into /docker-entrypoint-initdb.d/).
CREATE DATABASE brm_test OWNER brm;
