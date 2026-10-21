#!/bin/bash
# Drop and recreate the MariaDB database of the hosted instance, then reload it from a
# `spel export` directory. Local development uses SQLite (no reset needed: delete the file).
#
#   DB_PASSWORD=... ./reset_db.sh script-output/db-export/<label>
#
# Reads DB_NAME, DB_USER, DB_PASSWORD, DB_HOST from the environment (or spel/db/.env).
set -euo pipefail

cd "$(dirname "$0")"
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi
EXPORT_DIR="${1:?usage: reset_db.sh EXPORT_DIR}"
DB_NAME="${DB_NAME:-spelapp}"
DB_USER="${DB_USER:-djuser}"
DB_HOST="${DB_HOST:-127.0.0.1}"
: "${DB_PASSWORD:?set DB_PASSWORD in the environment or spel/db/.env}"

echo "About to DROP and RECREATE database '$DB_NAME' and user '$DB_USER' on $DB_HOST."
read -rp "This will DESTROY any data in '$DB_NAME'. Continue? (yes/NO) " ans
[[ "${ans:-}" == "yes" ]] || { echo "Aborted."; exit 1; }

echo "==> Resetting MariaDB schema and user..."
mariadb -u root -p <<SQL
DROP DATABASE IF EXISTS \`$DB_NAME\`;
CREATE DATABASE \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
DROP USER IF EXISTS '$DB_USER'@'localhost';
CREATE USER '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
SQL
echo "==> Done. Database: $DB_NAME  User: $DB_USER"

export DB_ENGINE=mysql
python3 manage.py migrate
python3 manage.py update_all_data "$EXPORT_DIR"
python3 manage.py import_presets
