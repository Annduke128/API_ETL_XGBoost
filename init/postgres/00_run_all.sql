-- Script chạy tất cả các file SQL theo thứ tự
-- Docker sẽ chạy các file .sql theo alphabetical order
-- File này import các file khác

\echo '========================================'
\echo 'Initializing Retail Database Schema'
\echo '========================================'

\echo '1. Creating base schema (01_init_schema.sql)...'
\i /docker-entrypoint-initdb.d/01_init_schema.sql

\echo '2. Creating inventory schema (02_inventory_schema.sql)...'
\i /docker-entrypoint-initdb.d/02_inventory_schema.sql

\echo '3. Creating inventory tables (03_inventory_tables.sql)...'
\i /docker-entrypoint-initdb.d/03_inventory_tables.sql

\echo '========================================'
\echo 'Schema initialization completed!'
\echo '========================================'
