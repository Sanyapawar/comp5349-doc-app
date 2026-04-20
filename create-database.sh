#!/bin/bash
# create-database.sh
# Run this script FROM your EC2 instance after RDS is set up.
# It creates the documents table in your PostgreSQL RDS database.

# Load variables from .env file if it exists (useful for local testing)
if [ -f "$(dirname "$0")/.env" ]; then
  # shellcheck disable=SC1091
  source "$(dirname "$0")/.env"
fi

DB_HOST="${DB_HOST}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-docdb}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD}"

export PGPASSWORD="$DB_PASSWORD"

echo "Creating database and table on RDS..."

# Create database if it doesn't exist
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || true

# Create the documents table
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOF
CREATE TABLE IF NOT EXISTS documents (
    id          SERIAL PRIMARY KEY,
    filename    VARCHAR(255) NOT NULL,
    s3_key      VARCHAR(500) NOT NULL,
    summary     TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
EOF

echo "Done! Table 'documents' is ready."

# Verify
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "\dt"
