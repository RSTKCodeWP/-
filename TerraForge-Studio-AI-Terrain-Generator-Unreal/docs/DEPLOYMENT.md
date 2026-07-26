# 🚀 Complete Deployment Guide - TerraForge Studio v4.x

**Version**: 4.0.0  
**Last Updated**: 22 October 2025

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Frontend Deployment](#frontend-deployment)
4. [Backend Deployment](#backend-deployment)
5. [Database Setup](#database-setup)
6. [Redis Configuration](#redis-configuration)
7. [Environment Variables](#environment-variables)
8. [SSL/HTTPS Setup](#ssl-https-setup)
9. [Monitoring & Logging](#monitoring--logging)
10. [Backup & Recovery](#backup--recovery)
11. [Scaling](#scaling)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- **Node.js**: 18.x or higher
- **Python**: 3.11 or higher
- **PostgreSQL**: 15 or higher
- **Redis**: 7.x or higher
- **Docker**: 24.x or higher (optional)
- **Nginx**: Latest stable (for production)

### System Requirements
- **CPU**: 4+ cores recommended
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 50GB+ SSD
- **OS**: Ubuntu 22.04 LTS, CentOS 8+, or Windows Server 2019+

---

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/terraforge-studio.git
cd terraforge-studio
```

### 2. Install Dependencies

#### Frontend
```bash
cd frontend-new
npm install
```

#### Backend
```bash
cd ../
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Frontend Deployment

### Development Build

```bash
cd frontend-new
npm run dev
```

### Production Build

```bash
npm run build
npm run preview  # Test production build locally
```

### Deploy to Static Hosting

#### Netlify
```bash
# Install Netlify CLI
npm install -g netlify-cli

# Deploy
netlify deploy --prod --dir=dist
```

#### Vercel
```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
vercel --prod
```

#### AWS S3 + CloudFront
```bash
# Build
npm run build

# Sync to S3
aws s3 sync dist/ s3://your-bucket-name --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"
```

---

## Backend Deployment

### Local Development

```bash
uvicorn realworldmapgen.api.main:app --reload --port 8000
```

### Production with Gunicorn

```bash
# Install Gunicorn
pip install gunicorn uvicorn[standard]

# Run with Gunicorn
gunicorn realworldmapgen.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### Systemd Service

Create `/etc/systemd/system/terraforge.service`:

```ini
[Unit]
Description=TerraForge API
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=terraforge
Group=terraforge
WorkingDirectory=/opt/terraforge
Environment="PATH=/opt/terraforge/venv/bin"
ExecStart=/opt/terraforge/venv/bin/gunicorn \
  realworldmapgen.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable terraforge
sudo systemctl start terraforge
sudo systemctl status terraforge
```

---

## Database Setup

### PostgreSQL Installation

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start service
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Create Database

```sql
-- Connect to PostgreSQL
sudo -u postgres psql

-- Create database and user
CREATE DATABASE terraforge;
CREATE USER terraforge WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE terraforge TO terraforge;

-- Exit
\q
```

### Run Migrations

```bash
# Install Alembic
pip install alembic

# Initialize
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head
```

---

## Redis Configuration

### Installation

```bash
# Ubuntu/Debian
sudo apt install redis-server

# Start service
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### Configure Redis

Edit `/etc/redis/redis.conf`:

```conf
bind 127.0.0.1
port 6379
maxmemory 256mb
maxmemory-policy allkeys-lru
```

Restart:
```bash
sudo systemctl restart redis-server
```

---

## Environment Variables

Create `.env` file:

```bash
# Application
APP_NAME=TerraForge Studio
APP_ENV=production
DEBUG=false
SECRET_KEY=your-super-secret-key-change-this

# Database
DATABASE_URL=postgresql://terraforge:password@localhost:5432/terraforge

# Redis
REDIS_URL=redis://localhost:6379/0

# API
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=https://yourdomain.com

# Storage
STORAGE_BACKEND=s3
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_S3_BUCKET=terraforge-data
AWS_REGION=us-east-1

# Authentication
JWT_SECRET=your-jwt-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# SSO
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-secret
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-secret

# Monitoring
SENTRY_DSN=your-sentry-dsn
MIXPANEL_TOKEN=your-mixpanel-token

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
RATE_LIMIT_PER_DAY=10000
```

---

## SSL/HTTPS Setup

### Let's Encrypt with Certbot

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal (already setup)
sudo certbot renew --dry-run
```

### Nginx Configuration

`/etc/nginx/sites-available/terraforge`:

```nginx
upstream backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Frontend
    location / {
        root /var/www/terraforge/dist;
        try_files $uri $uri/ /index.html;
    }

    # API
    location /api {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable and restart:
```bash
sudo ln -s /etc/nginx/sites-available/terraforge /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## Monitoring & Logging

### Setup Logging

Create `/var/log/terraforge/`:
```bash
sudo mkdir -p /var/log/terraforge
sudo chown terraforge:terraforge /var/log/terraforge
```

### Sentry Integration

Already configured in `sentry.ts`. Just set `SENTRY_DSN` in environment.

### System Monitoring

```bash
# Install monitoring tools
sudo apt install htop iotop nethogs

# View logs
sudo journalctl -u terraforge -f
tail -f /var/log/terraforge/app.log
```

---

## Backup & Recovery

### Database Backup

```bash
# Create backup script
cat > /opt/terraforge/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/backups/terraforge
DATE=$(date +%Y%m%d_%H%M%S)

# Database backup
pg_dump -U terraforge terraforge | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Keep last 7 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +7 -delete
EOF

chmod +x /opt/terraforge/backup.sh

# Add to crontab (daily at 2 AM)
0 2 * * * /opt/terraforge/backup.sh
```

---

## Scaling

### Horizontal Scaling

Use load balancer (Nginx, HAProxy, AWS ELB):

```nginx
upstream backend_cluster {
    least_conn;
    server backend1.local:8000;
    server backend2.local:8000;
    server backend3.local:8000;
}
```

### Docker Deployment

```yaml
# docker-compose.yml
version: '3.8'

services:
  frontend:
    build: ./frontend-new
    ports:
      - "80:80"
    depends_on:
      - backend

  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://terraforge:password@db:5432/terraforge
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: terraforge
      POSTGRES_USER: terraforge
      POSTGRES_PASSWORD: password
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

Deploy:
```bash
docker-compose up -d
```

---

## Troubleshooting

### Common Issues

**Frontend not loading:**
```bash
# Check build
npm run build
# Check nginx config
sudo nginx -t
# Check logs
sudo tail -f /var/log/nginx/error.log
```

**API errors:**
```bash
# Check service
sudo systemctl status terraforge
# Check logs
sudo journalctl -u terraforge -n 100
# Check database connection
psql -U terraforge -d terraforge
```

**High memory usage:**
```bash
# Check processes
htop
# Restart services
sudo systemctl restart terraforge
sudo systemctl restart redis
```

---

## Post-Deployment Checklist

- [ ] Frontend accessible via HTTPS
- [ ] API responding correctly
- [ ] WebSocket connections working
- [ ] Database migrations applied
- [ ] Redis cache functioning
- [ ] SSL certificates valid
- [ ] Monitoring active (Sentry)
- [ ] Backups configured
- [ ] Logs rotating properly
- [ ] Rate limiting active
- [ ] All environment variables set
- [ ] Security headers configured
- [ ] Firewall rules applied

---

## Support

- **Documentation**: https://docs.terraforge.studio
- **Discord**: https://discord.gg/terraforge
- **Email**: support@terraforge.studio
- **GitHub**: https://github.com/terraforge/studio

---

**Deployed**: 22 October 2025  
**Version**: 4.0.0  
**Status**: 🟢 Production Ready
