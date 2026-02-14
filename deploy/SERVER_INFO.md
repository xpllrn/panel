# Server Information & Configuration

## Server Details

### EC2 Instance
- **IP Address**: 13.201.60.211
- **Region**: ap-south-1 (Mumbai)
- **OS**: Ubuntu 24.04 LTS
- **Python Version**: 3.12.3
- **Domain**: delhiaamnagrik.org

### Security Groups
**Inbound Rules:**
- SSH (22) - 0.0.0.0/0
- HTTP (80) - 0.0.0.0/0
- HTTPS (443) - 0.0.0.0/0

**Outbound Rules:**
- All traffic - 0.0.0.0/0

---

## DNS Configuration

**Domain Registrar Settings:**

| Type | Name/Host | Value | TTL |
|------|-----------|-------|-----|
| A | @ | 13.201.60.211 | Automatic |
| A | www | 13.201.60.211 | Automatic |
| TXT | @ | zoho-verification=zb79382681.zmverify.zoho.in | Automatic |

---

## Application Structure

### Directory Layout
```
/var/www/app/
├── .env                    # Environment variables (NEVER commit to git)
├── manage.py              # Django management script
├── requirements.txt       # Python dependencies
├── gunicorn.sock         # Unix socket for Gunicorn (auto-created)
├── gunicorn-access.log   # Gunicorn access logs
├── gunicorn-error.log    # Gunicorn error logs
├── config/               # Django settings
│   ├── settings.py       # Main settings file
│   ├── urls.py          # URL routing
│   └── wsgi.py          # WSGI application
├── accounts/            # User authentication app
├── admin_portal/        # Admin interface app
├── member_portal/       # Member interface app
├── static/              # Static files (CSS, JS)
├── staticfiles/         # Collected static files (for production)
├── templates/           # HTML templates
├── media/              # User uploads
└── venv/               # Python virtual environment
```

---

## Configuration Files

### 1. Environment Variables (.env)
**Location**: `/var/www/app/.env`

```env
# Django Configuration
DEBUG=False
ALLOWED_HOSTS=*

# Supabase Configuration
SUPABASE_URL=https://gicpoymkcrszfcimaulb.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=sb_secret_5WMgshgdzITZfRonkTlPdg_d_DKBs8H

# Supabase Database Configuration
DB_NAME=postgres
DB_USER=postgres.gicpoymkcrszfcimaulb
DB_PASSWORD=kD4OfitBaoWhfP64
DB_HOST=aws-1-ap-south-1.pooler.supabase.com
DB_PORT=5432

SECRET_KEY=*iq2ejay&q8z%2-e+s7&^v$5bw0zq%c^5*000b@-78pka9$w8$
```

**Important**: Never commit this file to git!

---

### 2. Gunicorn Service
**Location**: `/etc/systemd/system/gunicorn.service`

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

**Commands:**
```bash
sudo systemctl start gunicorn      # Start service
sudo systemctl stop gunicorn       # Stop service
sudo systemctl restart gunicorn    # Restart service
sudo systemctl status gunicorn     # Check status
sudo systemctl enable gunicorn     # Enable on boot
```

---

### 3. Nginx Configuration
**Location**: `/etc/nginx/sites-available/app`

```nginx
server {
    server_name 13.201.60.211 delhiaamnagrik.org www.delhiaamnagrik.org;
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
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
        proxy_redirect off;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/delhiaamnagrik.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/delhiaamnagrik.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    if ($host = www.delhiaamnagrik.org) {
        return 301 https://$host$request_uri;
    }

    if ($host = delhiaamnagrik.org) {
        return 301 https://$host$request_uri;
    }

    listen 80;
    server_name 13.201.60.211 delhiaamnagrik.org www.delhiaamnagrik.org;
    return 404;
}
```

**Symlink**: `/etc/nginx/sites-enabled/app` → `/etc/nginx/sites-available/app`

**Commands:**
```bash
sudo nginx -t                      # Test configuration
sudo systemctl restart nginx       # Restart Nginx
sudo systemctl status nginx        # Check status
sudo tail -f /var/log/nginx/error.log    # View error logs
sudo tail -f /var/log/nginx/access.log   # View access logs
```

---

### 4. SSL Certificates (Let's Encrypt)
**Location**: `/etc/letsencrypt/live/delhiaamnagrik.org/`

**Files:**
- `fullchain.pem` - Full certificate chain
- `privkey.pem` - Private key
- `cert.pem` - Certificate only
- `chain.pem` - Chain only

**Auto-renewal**: Certbot automatically renews certificates

**Manual renewal:**
```bash
sudo certbot renew
sudo certbot renew --dry-run  # Test renewal
```

---

## Database (Supabase)

### Connection Details
- **Host**: aws-1-ap-south-1.pooler.supabase.com
- **Port**: 5432 (Session Pooler)
- **Database**: postgres
- **User**: postgres.gicpoymkcrszfcimaulb
- **Project URL**: https://gicpoymkcrszfcimaulb.supabase.co

### Important Notes
- Database is hosted on Supabase (PostgreSQL)
- Use Session Pooler for Django (port 5432)
- Do NOT use direct connection (IPv6 only)
- All migrations run against Supabase database

---

## Common Operations

### Deploy Code Updates
```bash
# SSH into server
ssh -i your-key.pem ubuntu@13.201.60.211

# Navigate to app directory
cd /var/www/app

# Activate virtual environment
source venv/bin/activate

# Pull latest code
git pull origin supabase

# Install new dependencies (if any)
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

### View Logs
```bash
# Gunicorn access logs
tail -f /var/www/app/gunicorn-access.log

# Gunicorn error logs
tail -f /var/www/app/gunicorn-error.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# System logs for Gunicorn service
sudo journalctl -u gunicorn -f
```

### Restart Services
```bash
# Restart Gunicorn only
sudo systemctl restart gunicorn

# Restart Nginx only
sudo systemctl restart nginx

# Restart both
sudo systemctl restart gunicorn nginx
```

### Check Service Status
```bash
# Check Gunicorn
sudo systemctl status gunicorn

# Check Nginx
sudo systemctl status nginx

# Check if socket exists
ls -la /var/www/app/gunicorn.sock

# Test Nginx config
sudo nginx -t
```

### Database Operations
```bash
cd /var/www/app
source venv/bin/activate

# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Django shell
python manage.py shell

# Database shell
python manage.py dbshell
```

---

## Troubleshooting

### Site Not Loading
1. Check Gunicorn status: `sudo systemctl status gunicorn`
2. Check Nginx status: `sudo systemctl status nginx`
3. Check socket exists: `ls -la /var/www/app/gunicorn.sock`
4. Check logs: `tail -50 /var/www/app/gunicorn-error.log`
5. Test Nginx config: `sudo nginx -t`

### 502 Bad Gateway
- Gunicorn is not running or crashed
- Socket file doesn't exist or has wrong permissions
- Check: `sudo systemctl restart gunicorn`

### 400 Bad Request
- ALLOWED_HOSTS not configured correctly
- Security settings conflict with proxy setup
- Check .env file and Django settings

### Static Files Not Loading
```bash
cd /var/www/app
source venv/bin/activate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
```

### Database Connection Issues
- Check .env file has correct credentials
- Test connection: `python manage.py dbshell`
- Verify Supabase pooler is accessible

---

## Security Checklist

- [x] DEBUG=False in production
- [x] Strong SECRET_KEY
- [x] ALLOWED_HOSTS configured
- [x] Firewall (Security Groups) enabled
- [x] SSH key-based authentication
- [x] SSL certificate installed (HTTPS)
- [x] Database credentials in .env (not in git)
- [x] .env file not in git repository
- [ ] Regular system updates
- [ ] Regular backups

---

## Backup & Recovery

### Backup Database
```bash
# Django dumpdata
cd /var/www/app
source venv/bin/activate
python manage.py dumpdata > backup_$(date +%Y%m%d).json
```

### Backup Media Files
```bash
cd /var/www/app
tar -czf media_backup_$(date +%Y%m%d).tar.gz media/
```

### Backup .env File
```bash
cat /var/www/app/.env
# Copy output to safe location
```

### Download Backups to Local Machine
```bash
# From your local machine
scp -i your-key.pem ubuntu@13.201.60.211:/var/www/app/backup_*.json ./
scp -i your-key.pem ubuntu@13.201.60.211:/var/www/app/media_backup_*.tar.gz ./
```

---

## Git Repository

- **Repository**: https://github.com/9zq3n/panel
- **Branch**: supabase
- **Clone Command**: `git clone https://github.com/9zq3n/panel.git`

---

## Contacts & Access

### SSH Access
```bash
ssh -i your-key.pem ubuntu@13.201.60.211
```

### Admin Access
- **URL**: https://delhiaamnagrik.org/admin/login/
- **Superuser**: adore
- **Password**: 9R@u2KqL

### Member Access
- **URL**: https://delhiaamnagrik.org/login/
- **URL**: https://delhiaamnagrik.org/member/login/

---

## Performance Optimization

### Gunicorn Workers
Current: 3 workers
Recommended: (2 x CPU cores) + 1

For 1 vCPU: 3 workers ✓
For 2 vCPU: 5 workers

### Nginx Caching
Consider adding caching for static files in Nginx config

### Database Connection Pooling
Already using Supabase Session Pooler ✓

---

## Monitoring

### Check Disk Space
```bash
df -h
```

### Check Memory Usage
```bash
free -h
```

### Check CPU Usage
```bash
htop  # Install with: sudo apt install htop
```

### Check Running Processes
```bash
ps aux | grep gunicorn
ps aux | grep nginx
```

---

## Notes

- Database is on Supabase - no local PostgreSQL
- Static files served by Nginx from `/var/www/app/staticfiles/`
- Media files served by Nginx from `/var/www/app/media/`
- Gunicorn runs as `ubuntu` user, group `www-data`
- SSL certificates auto-renew via Certbot
- Python virtual environment at `/var/www/app/venv/`

---

## Recent Changes & Fixes

### February 14, 2026 - Server Migration
- Migrated from old EC2 (3.27.117.228) to new EC2 (13.201.60.211)
- Updated DNS A records to point to new IP
- SSL certificates installed via Certbot
- Fixed Nginx configuration (removed duplicate Host header)
- Fixed Django template syntax errors in `templates/admin/base.html`
- Configured proxy headers for HTTPS support

### Known Issues Fixed
1. **Bad Request (400)**: Fixed by removing duplicate `proxy_set_header Host` in Nginx config
2. **Template Syntax Error**: Fixed broken `{% if %}` tags split across lines in admin base template
3. **HTTPS Redirect**: Configured `SECURE_PROXY_SSL_HEADER` for proper HTTPS detection behind Nginx

---

## Quick Reference Commands

### Deploy Latest Code
```bash
ssh -i your-key.pem ubuntu@13.201.60.211
cd /var/www/app
source venv/bin/activate
git pull origin supabase
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
```

### View Logs
```bash
# Gunicorn errors
tail -f /var/www/app/gunicorn-error.log

# Gunicorn access
tail -f /var/www/app/gunicorn-access.log

# Nginx errors
sudo tail -f /var/log/nginx/error.log
```

### Restart Services
```bash
sudo systemctl restart gunicorn nginx
```

---

**Last Updated**: February 15, 2026
**Server IP**: 13.201.60.211
**Domain**: https://delhiaamnagrik.org
**Status**: ✅ Live and Running
