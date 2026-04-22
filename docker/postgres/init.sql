-- Enable TimescaleDB extension for time-series price history
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Useful extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- trigram search on product titles
CREATE EXTENSION IF NOT EXISTS btree_gin;    -- composite indexes
