# 🖥️ Vendly EC2 Server — Command Reference

> **Server:** AWS EC2 `t3.micro` | **Region:** `ap-southeast-1` (Singapore)
> **IP:** `18.139.142.91` | **Domain:** `18.139.142.91.nip.io`
> **Stack:** Ubuntu + Nginx + Gunicorn + Flask + Python venv

---

## 📡 1. SSH — Connect to Server

```bash
# Connect to EC2 (from your local Windows terminal or PowerShell)
ssh -i "your-key.pem" ubuntu@18.139.142.91

# If permission error on Windows, fix key permissions:
icacls "your-key.pem" /inheritance:r /grant:r "%USERNAME%:R"
```

---

## 🔄 2. Deploy — Update Server After Git Push

### Quick Manual Update
```bash
cd /var/www/vendly-lk-web
git pull origin main
cd backend
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart vendly-backend
sudo systemctl status vendly-backend
```

### One-Command Deploy Script
```bash
# Run this after SSHing in — does everything automatically
./deploy.sh
```

#### Create/Edit the deploy script:
```bash
nano ~/deploy.sh
```
```bash
#!/bin/bash
set -e
echo "🚀 Pulling latest code..."
cd /var/www/vendly-lk-web
git pull origin main

echo "📦 Updating backend dependencies..."
cd backend
source .venv/bin/activate
pip install -r requirements.txt

echo "🔄 Restarting backend service..."
sudo systemctl restart vendly-backend

echo "✅ Done!"
sudo systemctl status vendly-backend --no-pager
```
```bash
chmod +x ~/deploy.sh
```

---

## ⚙️ 3. Gunicorn Service (Backend)

```bash
# Start the backend
sudo systemctl start vendly-backend

# Stop the backend
sudo systemctl stop vendly-backend

# Restart the backend (after code changes)
sudo systemctl restart vendly-backend

# Check if it's running + recent logs
sudo systemctl status vendly-backend

# Enable auto-start on server reboot
sudo systemctl enable vendly-backend

# Disable auto-start
sudo systemctl disable vendly-backend
```

---

## 🌐 4. Nginx (Reverse Proxy)

```bash
# Start Nginx
sudo systemctl start nginx

# Stop Nginx
sudo systemctl stop nginx

# Restart Nginx (after config changes)
sudo systemctl restart nginx

# Reload config without downtime
sudo systemctl reload nginx

# Check Nginx status
sudo systemctl status nginx

# Test Nginx config for syntax errors before reloading
sudo nginx -t

# Edit the Vendly site config
sudo nano /etc/nginx/sites-available/vendly-backend

# View Nginx error logs (last 50 lines)
sudo tail -50 /var/log/nginx/error.log

# View Nginx access logs (live)
sudo tail -f /var/log/nginx/access.log
```

---

## 📋 5. View Logs

```bash
# View backend logs (last 50 lines)
sudo journalctl -u vendly-backend -n 50 --no-pager

# Watch backend logs live (real-time)
sudo journalctl -u vendly-backend -f

# View backend logs since last boot
sudo journalctl -u vendly-backend -b

# View Nginx error log
sudo tail -50 /var/log/nginx/error.log

# Watch Nginx errors live
sudo tail -f /var/log/nginx/error.log
```

---

## 📊 6. Monitor RAM & CPU Usage

```bash
# Quick one-time RAM check (recommended)
free -h

# Quick CPU + process overview (press q to quit)
htop

# Full system monitor (press q to quit)
glances

# Check disk usage
df -h

# Check disk usage for a specific folder
du -sh /var/www/vendly-lk-web

# Check which processes use the most memory
ps aux --sort=-%mem | head -10

# Check which processes use the most CPU
ps aux --sort=-%cpu | head -10
```

---

## 🐍 7. Python Virtual Environment

```bash
# Go to backend folder
cd /var/www/vendly-lk-web/backend

# Activate virtual environment
source .venv/bin/activate

# Install a new package
pip install <package-name>

# Save installed packages to requirements.txt
pip freeze > requirements.txt

# Install all packages from requirements.txt
pip install -r requirements.txt

# Deactivate virtual environment
deactivate
```

---

## 🔑 8. Environment Variables (.env)

```bash
# Edit the backend .env file on the server
nano /var/www/vendly-lk-web/backend/.env

# View current env values (no secrets printed — safe check)
grep -E "FLASK_ENV|DEBUG|FRONTEND_ORIGINS" /var/www/vendly-lk-web/backend/.env

# After editing .env, always restart the backend
sudo systemctl restart vendly-backend
```

---

## 🔒 9. SSL Certificate (Certbot / Let's Encrypt)

```bash
# Check certificate status and expiry date
sudo certbot certificates

# Manually renew certificate (auto-renews, but just in case)
sudo certbot renew

# Test renewal without actually renewing
sudo certbot renew --dry-run

# Reinstall/reconfigure certificate for nip.io domain
sudo certbot --nginx -d 18.139.142.91.nip.io
```

---

## 🔁 10. Server Reboot & Shutdown

```bash
# Reboot the server
sudo reboot

# Shutdown the server (instance will stop on AWS)
sudo shutdown -h now

# Check server uptime
uptime
```

> ⚠️ After rebooting, `vendly-backend` and `nginx` will auto-restart if they are enabled via `systemctl enable`.

---

## 🧪 11. Test API Endpoints

```bash
# Test if the backend is reachable (health check)
curl https://18.139.142.91.nip.io/api/v1/health

# Test with CORS header (simulates a browser request)
curl -H "Origin: http://localhost:5173" https://18.139.142.91.nip.io/api/v1/health

# Test locally on the server (bypasses Nginx, talks to Gunicorn directly)
curl http://localhost:5000/api/v1/health
```

---

## 📁 12. File & Directory Navigation

```bash
# Project root
cd /var/www/vendly-lk-web

# Backend code
cd /var/www/vendly-lk-web/backend

# Backend API files
cd /var/www/vendly-lk-web/backend/app/api

# Nginx config
cd /etc/nginx/sites-available

# Systemd service file for the backend
cat /etc/systemd/system/vendly-backend.service
```

---

## 🛠️ 13. Edit the Systemd Service File

```bash
# Edit the service config (e.g. change workers, timeout)
sudo nano /etc/systemd/system/vendly-backend.service

# After editing, reload systemd and restart
sudo systemctl daemon-reload
sudo systemctl restart vendly-backend
```

---

## 🔥 14. Firewall (UFW)

```bash
# Check firewall status
sudo ufw status

# Allow HTTP and HTTPS (if locked out)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp

# Check open ports
ss -tlnp
```

---

## ⚡ Quick Reference Cheat Sheet

| Task | Command |
| :--- | :--- |
| SSH into server | `ssh -i key.pem ubuntu@18.139.142.91` |
| Deploy latest code | `./deploy.sh` |
| Restart backend | `sudo systemctl restart vendly-backend` |
| View backend logs | `sudo journalctl -u vendly-backend -n 50 --no-pager` |
| Watch live logs | `sudo journalctl -u vendly-backend -f` |
| Restart Nginx | `sudo systemctl restart nginx` |
| Test Nginx config | `sudo nginx -t` |
| Check RAM | `free -h` |
| Check disk | `df -h` |
| Test API health | `curl https://18.139.142.91.nip.io/api/v1/health` |
| Edit backend .env | `nano /var/www/vendly-lk-web/backend/.env` |
| Check SSL cert | `sudo certbot certificates` |
| Reboot server | `sudo reboot` |

---

*Last updated: September 2026 | Vendly.lk Backend Infrastructure*
