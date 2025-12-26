[日本語 (Japanese)](DEPLOYMENT.ja.md)

# Deployment Guide

This guide covers deploying the Docker MCP Gateway Console to production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Deployment Options](#deployment-options)
- [Option 1: Docker Compose (Recommended)](#option-1-docker-compose-recommended)
- [Option 2: Separate Services](#option-2-separate-services)
- [Option 3: Cloud Platforms](#option-3-cloud-platforms)
- [Security Hardening](#security-hardening)
- [Monitoring and Maintenance](#monitoring-and-maintenance)
- [Backup and Recovery](#backup-and-recovery)

## Prerequisites

Before deploying to production:

1. **Domain and SSL Certificate**
   - Register a domain name
   - Obtain SSL/TLS certificates (Let's Encrypt recommended)

2. **Server Requirements**
   - Linux server (Ubuntu 22.04 LTS recommended)
   - Minimum 2 CPU cores
   - Minimum 4GB RAM
   - 20GB+ disk space
   - Docker Engine 20.10+
   - Docker Compose v2+

3. **Bitwarden Setup**
   - Bitwarden account with API access
   - Bitwarden CLI installed on the server
   - API keys or master password for authentication

4. **Network Configuration**
   - Open ports 80 (HTTP) and 443 (HTTPS)
   - Configure firewall rules
   - Set up reverse proxy (Nginx or Caddy recommended)

## Deployment Options

### Option 1: Docker Compose (Recommended)

This is the simplest deployment method, suitable for single-server deployments.

#### Step 1: Prepare the Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin

# Install Bitwarden CLI
sudo npm install -g @bitwarden/cli

# Verify installations
docker --version
docker compose version
bw --version
```

#### Step 2: Clone and Configure

```bash
# Clone repository
git clone <repository-url>
cd docker-mcp-gateway-console

# Create production environment files
cp frontend/.env.local.example frontend/.env.local
cp backend/.env.example backend/.env

# Edit environment variables
nano frontend/.env.local
nano backend/.env
```

**frontend/.env.local:**
```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

**backend/.env:**
```env
BITWARDEN_CLI_PATH=/usr/local/bin/bw
DOCKER_HOST=unix:///var/run/docker.sock
SESSION_TIMEOUT_MINUTES=30
CATALOG_CACHE_TTL_SECONDS=3600
CORS_ORIGINS=https://yourdomain.com
LOG_LEVEL=WARNING

# Official Registry Pagination (optional - defaults shown)
CATALOG_OFFICIAL_MAX_PAGES=20
CATALOG_OFFICIAL_FETCH_TIMEOUT=60
CATALOG_OFFICIAL_PAGE_DELAY=100
```

#### Step 3: Create Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      - BITWARDEN_CLI_PATH=/usr/local/bin/bw
      - DOCKER_HOST=unix:///var/run/docker.sock
      - SESSION_TIMEOUT_MINUTES=30
      - CATALOG_CACHE_TTL_SECONDS=3600
      - CORS_ORIGINS=https://yourdomain.com
      - LOG_LEVEL=WARNING
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./backend/data:/app/data
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        - NEXT_PUBLIC_API_URL=https://api.yourdomain.com
    restart: unless-stopped
    depends_on:
      - backend
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/logs:/var/log/nginx
    depends_on:
      - frontend
      - backend
    networks:
      - app-network

networks:
  app-network:
    driver: bridge
```

#### Step 4: Configure Nginx

Create `nginx/nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream frontend {
        server frontend:3000;
    }

    upstream backend {
        server backend:8000;
    }

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    # Frontend
    server {
        listen 443 ssl http2;
        server_name yourdomain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        location / {
            proxy_pass http://frontend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_cache_bypass $http_upgrade;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

    # Backend API
    server {
        listen 443 ssl http2;
        server_name api.yourdomain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        location / {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_cache_bypass $http_upgrade;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # WebSocket support for log streaming
        location /api/containers/ {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 86400;
        }
    }
}
```

#### Step 5: Obtain SSL Certificates

Using Let's Encrypt with Certbot:

```bash
# Install Certbot
sudo apt install certbot

# Obtain certificates
sudo certbot certonly --standalone -d yourdomain.com -d api.yourdomain.com

# Copy certificates to nginx directory
sudo mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/
sudo chmod 644 nginx/ssl/*.pem
```

#### Step 6: Deploy

```bash
# Build and start services
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

#### Step 7: Set Up Auto-Renewal for SSL

```bash
# Add cron job for certificate renewal
sudo crontab -e

# Add this line to renew certificates monthly
0 0 1 * * certbot renew --quiet && docker compose -f /path/to/docker-compose.prod.yml restart nginx
```

### Option 2: Separate Services

Deploy frontend and backend on separate servers for better scalability.

#### Backend Server

```bash
# On backend server
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install as systemd service
sudo nano /etc/systemd/system/mcp-backend.service
```

**mcp-backend.service:**
```ini
[Unit]
Description=MCP Gateway Backend
After=network.target docker.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/mcp-gateway/backend
Environment="PATH=/opt/mcp-gateway/backend/venv/bin"
ExecStart=/opt/mcp-gateway/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable mcp-backend
sudo systemctl start mcp-backend
sudo systemctl status mcp-backend
```

#### Frontend Server

```bash
# On frontend server
cd frontend
npm install
npm run build

# Install PM2 for process management
npm install -g pm2

# Start with PM2
pm2 start npm --name "mcp-frontend" -- start
pm2 save
pm2 startup
```

### Option 3: Cloud Platforms

#### AWS Deployment

1. **Use ECS (Elastic Container Service)**
   - Create ECR repositories for frontend and backend
   - Push Docker images to ECR
   - Create ECS task definitions
   - Deploy to ECS Fargate

2. **Use EC2**
   - Launch EC2 instance (t3.medium or larger)
   - Follow Docker Compose deployment steps
   - Configure security groups (ports 80, 443)
   - Use Elastic IP for static IP address

#### Google Cloud Platform

1. **Use Cloud Run**
   - Build and push images to Google Container Registry
   - Deploy frontend and backend as separate Cloud Run services
   - Configure custom domains

2. **Use Compute Engine**
   - Create VM instance
   - Follow Docker Compose deployment steps

#### DigitalOcean

1. **Use App Platform**
   - Connect GitHub repository
   - Configure build settings
   - Deploy automatically on push

2. **Use Droplet**
   - Create Droplet (4GB RAM minimum)
   - Follow Docker Compose deployment steps

## Security Hardening

### 1. Firewall Configuration

```bash
# Using UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2. Docker Security

```bash
# Run Docker daemon in rootless mode (optional)
dockerd-rootless-setuptool.sh install

# Limit container resources
# Add to docker-compose.prod.yml:
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
```

### 3. Application Security

- Use strong session secrets
- Enable rate limiting
- Implement request validation
- Regular security updates

### 4. Network Security

- Use VPN for administrative access
- Implement IP whitelisting for sensitive endpoints
- Enable DDoS protection (Cloudflare, AWS Shield)

## Monitoring and Maintenance

### Health Checks

```bash
# Check service health
curl https://api.yourdomain.com/health

# Check frontend
curl https://yourdomain.com
```

### Logging

```bash
# View backend logs
docker compose -f docker-compose.prod.yml logs -f backend

# View frontend logs
docker compose -f docker-compose.prod.yml logs -f frontend

# View nginx logs
tail -f nginx/logs/access.log
tail -f nginx/logs/error.log
```

### Monitoring Tools

Consider integrating:
- **Prometheus + Grafana**: Metrics and dashboards
- **ELK Stack**: Log aggregation and analysis
- **Uptime Robot**: Uptime monitoring
- **Sentry**: Error tracking

### Updates

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# Clean up old images
docker image prune -a
```

## Backup and Recovery

### What to Backup

1. **Configuration files**
   - `.env` files
   - `docker-compose.prod.yml`
   - `nginx.conf`

2. **Application data**
   - Gateway configurations
   - Session data (if persisted)

3. **SSL certificates**
   - `/etc/letsencrypt/`

### Backup Script

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/mcp-gateway"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz \
  frontend/.env.local \
  backend/.env \
  docker-compose.prod.yml \
  nginx/

# Backup data
tar -czf $BACKUP_DIR/data_$DATE.tar.gz \
  backend/data/

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
```

### Automated Backups

```bash
# Add to crontab
crontab -e

# Daily backup at 2 AM
0 2 * * * /opt/mcp-gateway/backup.sh
```

### Recovery

```bash
# Stop services
docker compose -f docker-compose.prod.yml down

# Restore configuration
tar -xzf config_YYYYMMDD_HHMMSS.tar.gz

# Restore data
tar -xzf data_YYYYMMDD_HHMMSS.tar.gz

# Restart services
docker compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs

# Check Docker daemon
sudo systemctl status docker

# Check disk space
df -h
```

### SSL Certificate Issues

```bash
# Test certificate
openssl s_client -connect yourdomain.com:443

# Renew certificate manually
sudo certbot renew --force-renewal
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Check system resources
htop

# Optimize Docker
docker system prune -a
```

## Support

For additional help:
- Review application logs
- Check [GitHub Issues](repository-url/issues)
- Consult [Requirements Documentation](.kiro/specs/docker-mcp-gateway-console/requirements.md)
