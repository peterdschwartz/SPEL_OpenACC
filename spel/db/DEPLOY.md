# Deploying the explorer on AWS Lightsail (nginx + gunicorn + SQLite)

Notes for a Lightsail instance running Ubuntu with nginx in front of Django. Paths assume the repo
is cloned to `/srv/SPEL` and the database lives in `/srv/spel-data/`; adjust if yours differ. The
server does **not** need an E3SM checkout: snapshots are analyzed and exported on a development
machine and copied over.

The database is a single SQLite file (`explorer.sqlite3`) holding the snapshots, the namelist
presets, configuration evaluations, user accounts and category overrides. The site is almost all
reads, which SQLite handles well; see the end of this note for switching to MariaDB.

## 0. Before anything: secrets in git

`spel/db/.env`, `spel/db/local.env` and `spel/db/db.sqlite3` are tracked in git even though
`.gitignore` lists them (they were added before the ignore rule). Both env files hold a
`DJANGO_SECRET_KEY` and a `DB_PASSWORD`. Stop tracking them, and treat those values as public:

```bash
git rm --cached spel/db/.env spel/db/local.env spel/db/db.sqlite3
git commit -m "Stop tracking local env files and the dev database"
```

The old values stay in the git history, so generate a **new** secret key for the server (step 3).
`db.sqlite3` is an unused leftover; the app's database is `explorer.sqlite3`.

## 1. The instance

- **Image:** Ubuntu 24.04 LTS ("OS only"). Django 6 needs Python 3.12 or newer, which 24.04
  ships; Ubuntu 22.04's Python 3.10 is too old.
- **Size:** a plan with 1–2 GB of RAM is enough. The database is about 45 MB per snapshot, and the
  operating system keeps it in its file cache. Add a swap file on a 1 GB plan before loading
  snapshots on the server.
- **Static IP:** Lightsail console, Networking, "Create static IP", attach it to the instance. Without
  it the public IP changes when the instance stops.
- **Firewall:** in the instance's Networking tab, allow HTTP (80) and HTTPS (443) next to SSH (22).
- **Domain:** point an `A` record at the static IP (Lightsail can host the DNS zone too, under
  Domains & DNS).

If the instance was created from Lightsail's **Bitnami "NGINX" blueprint** instead of plain
Ubuntu, nginx lives under `/opt/bitnami/nginx/` (server blocks in
`/opt/bitnami/nginx/conf/server_blocks/`) and TLS is set up with `sudo /opt/bitnami/bncert-tool`
rather than certbot. The Django side below is the same.

## 2. Packages and code

```bash
sudo apt update
sudo apt install -y git python3-venv python3-dev build-essential nginx certbot python3-certbot-nginx

sudo mkdir -p /srv && sudo chown $USER /srv
git clone https://github.com/peterdschwartz/SPEL.git /srv/SPEL
cd /srv/SPEL
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[db]' gunicorn
```

SQLite is part of Python; there is no database server to install.

## 3. Settings: `spel/db/.env` on the server

Settings are read from `spel/db/.env` (template `.env.example`). Create it fresh:

```bash
cd /srv/SPEL/spel/db
cp .env.example .env
python4 -c "import secrets; print(secrets.token_urlsafe(50))"   # -> DJANGO_SECRET_KEY
chmod 600 .env
```

The values that matter in production (`<host>` is your domain):

```ini
DJANGO_SECRET_KEY=<the generated key>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<host>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<host>
DJANGO_LOG_LEVEL=INFO

# after TLS works (step 7):
DJANGO_SECURE_PROXY_SSL_HEADER=true
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_HSTS_SECONDS=3600            # raise to 31536000 once everything works

# database: leave DB_ENGINE unset for SQLite
SPEL_DB_PATH=/srv/spel-data/explorer.sqlite3

STATIC_ROOT=/srv/SPEL/spel/db/staticfiles

# accounts: anyone can browse; signing up is only needed for the namelist editor
REGISTRATION_OPEN=False             # or True with an INVITE_CODE
```

Notes:

- Only the exact word `true` turns a flag on; anything else is off.
- `DJANGO_HSTS_SECONDS` defaults to a year and is sent with `preload`. Start low: a mistake with a
  year-long HSTS header locks browsers into HTTPS for that host.
- Leave the `DJANGO_SECURE_*` lines out until the certificate is in place, or the site redirects to
  an HTTPS that doesn't answer yet.
- Keep the database outside the git checkout, so a `git pull` or a fresh clone never touches it.

## 4. The database

The data directory must be writable by the user gunicorn runs as (`ubuntu` below): SQLite writes
two companion files (`explorer.sqlite3-wal` and `-shm`) next to the database while the site runs.

```bash
sudo mkdir -p /srv/spel-data && sudo chown ubuntu:ubuntu /srv/spel-data
```

There are two ways to get a database there. Run the commands from `/srv/SPEL/spel/db` with the
venv active.

### A. Copy the one you built locally (quickest)

Your local `spel/db/explorer.sqlite3` already has the snapshots and presets loaded. Make a
consistent copy (safe even while your local `runserver` is running) and send it:

```bash
# on the development machine, from the SPEL repo
python -c "import sqlite3; s=sqlite3.connect('spel/db/explorer.sqlite3'); d=sqlite3.connect('/tmp/explorer.sqlite3'); s.backup(d); d.close()"
rsync -av /tmp/explorer.sqlite3 <server>:/srv/spel-data/
```

Then on the server bring its tables up to the deployed code and create an admin account (local
accounts came along in the copy; remove any you don't want in `/admin`):

```bash
python manage.py migrate
python manage.py createsuperuser
```

### B. Build it on the server from export directories

On the development machine (which has the E3SM checkouts):

```bash
spel analyze --srcroot ~/climate-projects/master_E3SM
spel export  --srcroot ~/climate-projects/master_E3SM      # -> script-output/db-export/master@<commit>/
rsync -av script-output/db-export/master@<commit> <server>:/srv/exports/
```

On the server:

```bash
python manage.py migrate                                           # creates the file and its tables
python manage.py update_all_data /srv/exports/master@<commit>
python manage.py update_all_data /srv/exports/<branch>@<commit>   # as many as you like
python manage.py import_presets --default cnprdctcbc               # namelist presets
python manage.py createsuperuser
```

### Either way

```bash
python manage.py collectstatic --noinput       # copy CSS/JS into STATIC_ROOT for nginx
python manage.py update_all_data --list        # what is loaded
```

### Adding or refreshing a snapshot later

Copy the export directory over and load it; the site keeps serving pages while it loads.

```bash
python manage.py update_all_data /srv/exports/<label>             # a new snapshot
python manage.py update_all_data /srv/exports/<label> --replace   # same label: replace it (overrides are kept)
sudo systemctl restart spel-explorer                              # results are cached per worker
```

To replace the whole database with a new copy from your machine (option A), stop the service
first, remove the old `-wal`/`-shm` files with it, then start it again:

```bash
sudo systemctl stop spel-explorer
rm -f /srv/spel-data/explorer.sqlite3-wal /srv/spel-data/explorer.sqlite3-shm
rsync -av /tmp/explorer.sqlite3 /srv/spel-data/      # (copied up as in option A)
python manage.py migrate
sudo systemctl start spel-explorer
```

Copying the new file in place but keeping the old companion files can corrupt it.

### Backups

```bash
python -c "import sqlite3,datetime; s=sqlite3.connect('/srv/spel-data/explorer.sqlite3'); d=sqlite3.connect(f'/home/ubuntu/explorer-{datetime.date.today()}.sqlite3'); s.backup(d); d.close()"
```

This is safe while the site runs; a plain `cp` of a live database is not. The snapshots can always
be reloaded from the export directories; the backup matters for user accounts, custom
configurations and category overrides. A Lightsail instance snapshot also covers it.

## 5. gunicorn as a service

`/etc/systemd/system/spel-explorer.service`:

```ini
[Unit]
Description=SPEL ELM explorer (gunicorn)
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/srv/SPEL/spel
ExecStart=/srv/SPEL/.venv/bin/gunicorn db.spel.wsgi:application \
    --workers 3 --timeout 120 --bind unix:/run/spel-explorer/gunicorn.sock
RuntimeDirectory=spel-explorer
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now spel-explorer
sudo systemctl status spel-explorer
journalctl -u spel-explorer -f          # Django's log
```

The module path is `db.spel.wsgi` run from `/srv/SPEL/spel`, the same layout `manage.py` uses.
`--timeout 120` leaves room for the first request under a new configuration, which evaluates every
namelist-gated `if` once and can take a few seconds. Several workers are fine with SQLite: the app
opens it in WAL mode, so readers run in parallel and a writer waits for at most 30 seconds.

## 6. nginx

`/etc/nginx/sites-available/spel-explorer`:

```nginx
server {
    listen 80;
    server_name <host>;

    location /static/ {
        alias /srv/SPEL/spel/db/staticfiles/;
        expires 7d;
    }

    location / {
        proxy_pass http://unix:/run/spel-explorer/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/spel-explorer /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

nginx (user `www-data`) must be able to read `staticfiles/` and every directory above it:
`chmod o+x /srv /srv/SPEL /srv/SPEL/spel /srv/SPEL/spel/db` if needed. It never touches the
database.

Static files are referenced with a `?v=<mtime>` suffix, so browsers pick up new CSS/JS after each
`collectstatic` without a hard reload; `expires 7d` is safe.

## 7. HTTPS

```bash
sudo certbot --nginx -d <host>          # edits the nginx file, adds the 443 server and renewals
```

Then add the `DJANGO_SECURE_*` lines from step 3 to `.env` and `sudo systemctl restart
spel-explorer`. certbot renews on its own (`systemctl list-timers | grep certbot`).

## 8. Updating the site

```bash
cd /srv/SPEL && git pull
. .venv/bin/activate && pip install -e '.[db]'
cd spel/db
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart spel-explorer
```

## Troubleshooting

| Symptom | Usual cause |
|---|---|
| 400 Bad Request | the host isn't in `DJANGO_ALLOWED_HOSTS` |
| 403 CSRF verification failed on sign-in or forms | `DJANGO_CSRF_TRUSTED_ORIGINS` lacks `https://<host>` |
| Endless redirects after enabling HTTPS | `DJANGO_SECURE_PROXY_SSL_HEADER=true` missing, or nginx not sending `X-Forwarded-Proto` |
| Pages without styling | `collectstatic` not run, wrong `alias` path, or `www-data` can't read the directory |
| 502 Bad Gateway | gunicorn not running: `journalctl -u spel-explorer` |
| `DJANGO_SECRET_KEY must be set` at start | `.env` not found or not readable by the service user |
| `unable to open database file` or `attempt to write a readonly database` | `/srv/spel-data` (the directory, not only the file) isn't writable by the service user, or `SPEL_DB_PATH` is wrong |
| `no such table` | `python manage.py migrate` not run against this file |
| `database is locked` | a long write (a snapshot load) held the lock for more than 30 s; retry after it finishes |
| A reloaded snapshot still shows old data | restart the service (results are cached in each worker) |

## Switching to MariaDB later

Worth it only with many concurrent writers or the database on its own machine. No code changes:

1. `sudo apt install mariadb-server libmariadb-dev pkg-config`, then
   `pip install -e '.[db,mysql]'`.
2. `sudo mariadb-secure-installation`; add `max_allowed_packet=64M` under `[mysqld]` in
   `/etc/mysql/mariadb.conf.d/99-spel.cnf` (rows carry routine source text) and restart MariaDB.
3. Create the database and user:

   ```bash
   sudo mariadb <<'SQL'
   CREATE DATABASE spelapp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'djuser'@'localhost' IDENTIFIED BY '<password>';
   GRANT ALL PRIVILEGES ON spelapp.* TO 'djuser'@'localhost';
   FLUSH PRIVILEGES;
   SQL
   ```

4. In `.env`: `DB_ENGINE=mysql`, `DB_NAME=spelapp`, `DB_USER=djuser`, `DB_PASSWORD=<password>`,
   `DB_HOST=127.0.0.1`, `DB_PORT=3306`.
5. `migrate`, then load the snapshots and presets as in option B. `reset_db.sh EXPORT_DIR` does
   steps 3 and 5 for one export (it asks for the MariaDB root password and confirmation). User
   accounts and custom configurations can be moved from the SQLite file with
   `python manage.py dumpdata auth app.ConfigProfile > users.json` (run with the old settings) and
   `loaddata users.json` (with the new); hand-made category overrides have to be re-entered.
