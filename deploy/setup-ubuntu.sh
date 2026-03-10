#!/bin/bash
# Optional one-time setup for HR Job Portal on Ubuntu.
# Edit APP_ROOT and DB_PASSWORD below. Run with: sudo bash deploy/setup-ubuntu.sh
set -e

APP_ROOT="${APP_ROOT:-/var/www/hr-job-portal}"
DB_PASSWORD="${DB_PASSWORD:-change_me_please}"

echo "Installing system packages..."
apt update
apt install -y python3 python3-venv python3-pip nodejs npm nginx postgresql postgresql-contrib

echo "Creating PostgreSQL user and database..."
sudo -u postgres psql -c "CREATE USER jobportal WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE jobportal OWNER jobportal;" 2>/dev/null || true

echo "Setting up backend venv..."
cd "$APP_ROOT/backend"
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

echo "Building frontend (same-origin API)..."
cd "$APP_ROOT/frontend"
npm ci
VITE_API_URL= npm run build

echo "Fixing ownership for www-data..."
chown -R www-data:www-data "$APP_ROOT"

echo "Installing systemd service..."
sed "s|/var/www/hr-job-portal|$APP_ROOT|g" "$APP_ROOT/deploy/hr-job-portal-backend.service" > /etc/systemd/system/hr-job-portal-backend.service
systemctl daemon-reload
systemctl enable hr-job-portal-backend

echo "Nginx: copy site config (already set for 192.168.1.27), then enable:"
echo "  sudo cp $APP_ROOT/deploy/nginx-hr-job-portal.conf /etc/nginx/sites-available/hr-job-portal"
echo "  sudo ln -sf /etc/nginx/sites-available/hr-job-portal /etc/nginx/sites-enabled/"
echo "  sudo nginx -t && sudo systemctl reload nginx"
echo ""
echo "Create backend .env with POSTGRES_HOST=localhost, POSTGRES_USER=jobportal, POSTGRES_PASSWORD=..., FLASK_DEBUG=false, FRONTEND_URL(s)=http://192.168.1.27"
echo "Then: sudo systemctl start hr-job-portal-backend"
echo "Access on LAN: http://192.168.1.27"
echo "Done."
