#!/usr/bin/env bash
# Copy the old Render Postgres into Neon. Run on the server (needs Docker).
#   SOURCE_URL='postgresql://user:pass@host/db' TARGET_URL='postgresql://neondb_owner:pass@ep-xxxx.aws.neon.tech/neondb?sslmode=require' ./migrate-db.sh
# Use plain postgresql:// URLs here (not +asyncpg), with Neon's direct (non-pooler) host.
# Run it BEFORE the API's first start, otherwise startup seeds default users into Neon
# and the restore will conflict.
set -euo pipefail
: "${SOURCE_URL:?set SOURCE_URL}" "${TARGET_URL:?set TARGET_URL}"
dump=/tmp/docintel.dump
docker run --rm -v /tmp:/tmp postgres:17-alpine \
  pg_dump "$SOURCE_URL" --format=custom --no-owner --no-acl -f "$dump"
docker run --rm -v /tmp:/tmp postgres:17-alpine \
  pg_restore --dbname="$TARGET_URL" --no-owner --no-acl --clean --if-exists "$dump"
rm -f "$dump"
echo "Migration complete."
