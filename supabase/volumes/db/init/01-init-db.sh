#!/bin/bash
# Database initialization script for PostgreSQL
set -e

# Create database if it doesn't exist
psql -v "$DATABASE_URL" -c "
CREATE DATABASE IF NOT EXISTS ezonboard;
" || echo "Database creation skipped (already exists)"

# Create keycloak database if it doesn't exist
psql -v "$DATABASE_URL" -c "
CREATE DATABASE IF NOT EXISTS keycloak;
" || echo "Keycloak database creation skipped (already exists)"

echo "Database initialization completed successfully"