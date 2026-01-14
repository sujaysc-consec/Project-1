-- Drop tables in correct order (purchases first due to FK constraint)
DROP TABLE IF EXISTS purchases;
DROP TABLE IF EXISTS inventory;
