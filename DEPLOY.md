# Deploying HR Job Portal on Ubuntu

This guide covers deploying the HR Job Portal on an Ubuntu server with Nginx, Gunicorn, and PostgreSQL.

**This setup is for local private network:** server IP **192.168.1.27**. Clients on the same LAN access the app at `http://192.168.1.27`.

## Prerequisites

- Ubuntu 22.04 or 24.04
- Root or sudo access
- Server IP on LAN: 192.168.1.27 (already set in Nginx config)

## 1. Server dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nodejs npm nginx postgresql postgresql-contrib
```

(Use Node 18+ from NodeSource if your Ubuntu has an older Node.)

## 2. Application directory

Clone or copy the app to the server, e.g.:

```bash
sudo mkdir -p /var/www
sudo git clone https://github.com/YOUR_ORG/HR-Job-Portal-App.git /var/www/hr-job-portal
# Or upload via rsync/scp
```

Set ownership so the service user can read files (and write logs if needed):

```bash
sudo chown -R www-data:www-data /var/www/hr-job-portal
```

## 3. PostgreSQL database

Create a database and user:

```bash
sudo -u postgres psql -c "CREATE USER jobportal WITH PASSWORD 'your_secure_password';"
sudo -u postgres psql -c "CREATE DATABASE jobportal OWNER jobportal;"
```

## 4. Backend setup

```bash
cd /var/www/hr-job-portal/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create production `.env` (copy from `.env.example` or existing `.env` and edit):

- `FLASK_DEBUG=false`
- `FRONTEND_URL` and `FRONTEND_URLS`: for local LAN use `http://192.168.1.27` (e.g. `FRONTEND_URL=http://192.168.1.27`, `FRONTEND_URLS=http://192.168.1.27`)
- PostgreSQL: `POSTGRES_HOST=localhost`, `POSTGRES_PORT=5432`, `POSTGRES_USER=jobportal`, `POSTGRES_PASSWORD=...`, `POSTGRES_DB=jobportal`
- `JWT_SECRET`: use a long random secret
- Configure email and any other variables as needed

Ensure `.env` is readable by the process that runs Gunicorn (e.g. `www-data`):

```bash
sudo chown www-data:www-data /var/www/hr-job-portal/backend/.env
sudo chmod 600 /var/www/hr-job-portal/backend/.env
```

## 5. Frontend build (production)

Build with **same-origin API** (no separate API URL) so Nginx can proxy `/api`:

```bash
cd /var/www/hr-job-portal/frontend
npm ci
VITE_API_URL= npm run build
```

This produces `frontend/dist`. Keep `VITE_API_URL` empty so the app uses relative URLs (e.g. `/api/...`).

## 6. Systemd service (Gunicorn)

```bash
sudo cp /var/www/hr-job-portal/deploy/hr-job-portal-backend.service /etc/systemd/system/
# If the app is not in /var/www/hr-job-portal, edit the service file and set WorkingDirectory and PATH/ExecStart
sudo systemctl daemon-reload
sudo systemctl enable hr-job-portal-backend
sudo systemctl start hr-job-portal-backend
sudo systemctl status hr-job-portal-backend
```

## 7. Nginx

Copy the site config and enable it (config is already set for **192.168.1.27**):

```bash
sudo cp /var/www/hr-job-portal/deploy/nginx-hr-job-portal.conf /etc/nginx/sites-available/hr-job-portal
```

Edit only if the app is not in `/var/www/hr-job-portal`: change the `root` path and any path in comments.

Then:

```bash
sudo ln -s /etc/nginx/sites-available/hr-job-portal /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

HTTPS is optional on a private LAN. If you use it, add SSL to the Nginx server block or use Certbot with a local hostname.

## 8. Firewall (optional on private LAN)

If `ufw` is enabled, allow HTTP and SSH so other machines on the LAN can reach the app:

```bash
sudo ufw allow 22
sudo ufw allow 80
sudo ufw enable
```

## 9. Verify

- From any machine on the same network, open **http://192.168.1.27** — you should see the frontend.
- Open **http://192.168.1.27/health** — should return backend health JSON.
- Log in and use the app; API calls go to `/api` and are proxied to Gunicorn.

## Production checklist (local LAN)

- [ ] `FLASK_DEBUG=false` in backend `.env`
- [ ] `FRONTEND_URL` / `FRONTEND_URLS` set to `http://192.168.1.27`
- [ ] Strong `JWT_SECRET` and DB password
- [ ] Frontend built with `VITE_API_URL=` (empty)
- [ ] DB and `.env` permissions restricted

## Optional: setup script

For a quick first-time setup (edit paths and passwords before running):

```bash
sudo bash /var/www/hr-job-portal/deploy/setup-ubuntu.sh
```

See `deploy/setup-ubuntu.sh` for what it installs and configures.
