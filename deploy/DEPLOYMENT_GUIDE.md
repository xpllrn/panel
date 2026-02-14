# EC2 Deployment Guide - Complete Commands

## Prerequisites
- EC2 instance running Ubuntu 22.04
- Security groups configured (ports 22, 80, 443, 8000)
- SSH key pair downloaded (.pem file)

---

## Step 1: Connect to EC2

```bash
# On your local machine
# Replace with your .pem file path and EC2 public IP
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@your-ec2-public-ip
```

---

## Step 2: Initial Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip python3.11-dev

# Install system dependencies
sudo apt install -y build-essential libpq-dev nginx git curl

# Install PostgreSQL client (for Supabase connection testing)
sudo apt install -y postgresql-client
```

---

## Step 3: Create Application Directory

```bash
# Create app directory
sudo mkdir -p /var/www/app
sudo chown -R $USER:$USER /var/www/app
cd /var/www/app
```

---

## Step 4: Upload Your Code

### Option A: Using Git (Recommended)

```bash
cd /var/www/app
git clone <your-repo-url> .
```

### Option B: Using SCP from Local Machine

```bash
# On your LOCAL machine (not EC2)
# From your project directory
scp -i your-key.pem -r * ubuntu@your-ec2-ip:/var/www/app/
```

---

## Step 5: Setup Python Environment

```bash
cd /var/www/app

# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install Gunicorn
pip install gunicorn
```

---

## Step 6: Configure Environment Variables

```bash
cd /var/www/app

# Create .env file
nano .env
```

**Paste this and update with your actual values:**

```env
SECRET_KEY=your-production-secret-key-here-make-it-long-and-random
DEBUG=False
ALLOWED_HOSTS=your-ec2-public-ip,your-domain.com

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

DB_NAME=postgres
DB_USER=postgres.your-project-ref
DB_PASSWORD=your-db-password
DB_HOST=aws-0-region.pooler.supabase.com
DB_PORT=5432
```

**Save and exit:** Press `Ctrl+X`, then `Y`, then `Enter`

---

## Step 7: Django Setup

```bash
cd /var/www/app
source venv/bin/activate

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Test if Django works
python manage.py runserver 0.0.0.0:8000
```

**Test in browser:** `http://your-ec2-ip:8000`

Press `Ctrl+C` to stop the test server.

---

## Step 8: Configure Gunicorn

```bash
# Test Gunicorn
cd /var/www/app
source venv/bin/activate
gunicorn --bind 0.0.0.0:8000 config.wsgi:application
```

**Test in browser:** `http://your-ec2-ip:8000`

Press `Ctrl+C` to stop.

### Create Gunicorn systemd service

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

**Paste this:**

```ini
[Unit]
Description=Gunicorn daemon for Django app
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/var/www/app
Environment="PATH=/var/www/app/venv/bin"
EnvironmentFile=/var/www/app/.env
ExecStart=/var/www/app/venv/bin/gunicorn \
          --workers 3 \
          --bind unix:/var/www/app/gunicorn.sock \
          --timeout 120 \
          --access-logfile /var/www/app/gunicorn-access.log \
          --error-logfile /var/www/app/gunicorn-error.log \
          config.wsgi:application

[Install]
WantedBy=multi-user.target
```

**Save and exit:** `Ctrl+X`, `Y`, `Enter`

```bash
# Start and enable Gunicorn
sudo systemctl start gunicorn
sudo systemctl enable gunicorn

# Check status
sudo systemctl status gunicorn

# If there are errors, check logs
sudo journalctl -u gunicorn -n 50
```

---

## Step 9: Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/app
```

**Paste this:**

```nginx
server {
    listen 80;
    server_name your-ec2-public-ip your-domain.com;

    client_max_body_size 10M;

    location = /favicon.ico { 
        access_log off; 
        log_not_found off; 
    }

    location /static/ {
        alias /var/www/app/staticfiles/;
    }

    location /media/ {
        alias /var/www/app/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/app/gunicorn.sock;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_redirect off;
    }
}
```

**Save and exit:** `Ctrl+X`, `Y`, `Enter`

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx

# Enable Nginx to start on boot
sudo systemctl enable nginx
```

---

## Step 10: Configure Firewall (UFW)

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 'OpenSSH'
sudo ufw allow 'Nginx Full'

# Enable firewall
sudo ufw --force enable

# Check status
sudo ufw status
```

---

## Step 11: Test Your Application

Open browser and visit: `http://your-ec2-public-ip`

Your Django app should be live!

---

## Step 12: Setup SSL Certificate (Optional but Recommended)

### If you have a domain name:

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate (replace with your domain)
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Test auto-renewal
sudo certbot renew --dry-run
```

---

## Useful Commands for Management

### View Logs

```bash
# Gunicorn logs
sudo journalctl -u gunicorn -f

# Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Application logs
tail -f /var/www/app/gunicorn-error.log
```

### Restart Services

```bash
# After code changes
cd /var/www/app
source venv/bin/activate
git pull  # if using git
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

### Check Service Status

```bash
sudo systemctl status gunicorn
sudo systemctl status nginx
```

### Stop/Start Services

```bash
sudo systemctl stop gunicorn
sudo systemctl start gunicorn
sudo systemctl restart gunicorn

sudo systemctl stop nginx
sudo systemctl start nginx
sudo systemctl restart nginx
```

---

## Troubleshooting

### Gunicorn won't start

```bash
# Check logs
sudo journalctl -u gunicorn -n 100

# Check if socket file exists
ls -la /var/www/app/gunicorn.sock

# Check permissions
sudo chown -R ubuntu:www-data /var/www/app
```

### Nginx 502 Bad Gateway

```bash
# Check if Gunicorn is running
sudo systemctl status gunicorn

# Check Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Restart both services
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

### Static files not loading

```bash
cd /var/www/app
source venv/bin/activate
python manage.py collectstatic --noinput

# Check permissions
sudo chown -R ubuntu:www-data /var/www/app/staticfiles
sudo chmod -R 755 /var/www/app/staticfiles
```

### Database connection issues

```bash
# Test Supabase connection
cd /var/www/app
source venv/bin/activate
python manage.py dbshell

# Check .env file
cat .env

# Test with Django shell
python manage.py shell
>>> from django.db import connection
>>> connection.ensure_connection()
>>> print("Connected!")
```

---

## Security Checklist

- [ ] DEBUG=False in production
- [ ] Strong SECRET_KEY
- [ ] ALLOWED_HOSTS configured
- [ ] Firewall (UFW) enabled
- [ ] SSH key-based authentication only
- [ ] SSL certificate installed
- [ ] Regular system updates
- [ ] Database credentials secured in .env
- [ ] .env file not in git repository

---

## Updating Your Application

```bash
# SSH into EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Navigate to app directory
cd /var/www/app

# Activate virtual environment
source venv/bin/activate

# Pull latest code (if using git)
git pull

# Install any new dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart Gunicorn
sudo systemctl restart gunicorn

# Check status
sudo systemctl status gunicorn
```

---

## Backup Strategy

```bash
# Backup database (Supabase handles this automatically)
# But you can export data:
cd /var/www/app
source venv/bin/activate
python manage.py dumpdata > backup_$(date +%Y%m%d).json

# Backup media files
tar -czf media_backup_$(date +%Y%m%d).tar.gz media/

# Download to local machine
# On your local machine:
scp -i your-key.pem ubuntu@your-ec2-ip:/var/www/app/backup_*.json ./
```

---

## Performance Optimization

```bash
# Increase Gunicorn workers (2-4 x CPU cores)
sudo nano /etc/systemd/system/gunicorn.service
# Change --workers 3 to --workers 5 (for 2 vCPU)

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart gunicorn

# Enable Nginx gzip compression
sudo nano /etc/nginx/nginx.conf
# Add in http block:
# gzip on;
# gzip_types text/plain text/css application/json application/javascript;

sudo systemctl restart nginx
```

---

## Monitoring

```bash
# Install htop for system monitoring
sudo apt install -y htop
htop

# Check disk usage
df -h

# Check memory usage
free -h

# Check running processes
ps aux | grep gunicorn
ps aux | grep nginx
```

---

## Done!

Your Django app is now deployed on EC2 with:
- ✅ Nginx as reverse proxy
- ✅ Gunicorn as WSGI server
- ✅ Systemd for auto-restart
- ✅ Static files served efficiently
- ✅ Production-ready configuration

Visit: `http://your-ec2-public-ip`
