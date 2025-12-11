[English](DEPLOYMENT.md)

# デプロイメントガイド

このガイドでは、Docker MCP Gateway Consoleを本番環境にデプロイする方法について説明します。

## 目次

- [前提条件](#前提条件)
- [デプロイオプション](#デプロイオプション)
- [オプション 1: Docker Compose（推奨）](#オプション-1-docker-compose推奨)
- [オプション 2: 個別のサービス](#オプション-2-個別のサービス)
- [オプション 3: クラウドプラットフォーム](#オプション-3-クラウドプラットフォーム)
- [セキュリティ強化](#セキュリティ強化)
- [監視とメンテナンス](#監視とメンテナンス)
- [バックアップと復旧](#バックアップと復旧)

## 前提条件

本番環境へのデプロイ前に以下が必要です :

1. **ドメインとSSL証明書**
   - ドメイン名の登録
   - SSL/TLS証明書の取得（Let's Encrypt推奨）

2. **サーバー要件**
   - Linuxサーバー（Ubuntu 22.04 LTS推奨）
   - 最小 2 CPUコア
   - 最小 4GB RAM
   - 20GB+ ディスク容量
   - Docker Engine 20.10+
   - Docker Compose v2+

3. **Bitwarden設定**
   - APIアクセス可能なBitwardenアカウント
   - サーバーにBitwarden CLIがインストールされていること
   - 認証用のAPIキーまたはマスターパスワード

4. **ネットワーク設定**
   - ポート 80 (HTTP) および 443 (HTTPS) の開放
   - ファイアウォールルールの設定
   - リバースプロキシのセットアップ（NginxまたはCaddy推奨）

## デプロイオプション

### オプション 1: Docker Compose（推奨）

これは最もシンプルなデプロイ方法で、単一サーバーでのデプロイに適しています。

#### ステップ 1: サーバーの準備

```bash
# システムの更新
sudo apt update && sudo apt upgrade -y

# Dockerのインストール
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Composeのインストール
sudo apt install docker-compose-plugin

# Bitwarden CLIのインストール
sudo npm install -g @bitwarden/cli

# インストールの確認
docker --version
docker compose version
bw --version
```

#### ステップ 2: クローンと設定

```bash
# リポジトリのクローン
git clone <repository-url>
cd docker-mcp-gateway-console

# 本番環境ファイルの作成
cp frontend/.env.local.example frontend/.env.local
cp backend/.env.example backend/.env

# 環境変数の編集
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
```

#### ステップ 3: 本番用Docker Composeの作成

`docker-compose.prod.yml` を作成します :

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

> 補足: 実際の `docker-compose.prod.yml`（および開発/テスト用 Compose）では、Bitwarden CLI のログインキャッシュを `/root/.config/Bitwarden CLI` と `/root/.cache/Bitwarden CLI` に保存するために `bw-cli-config` と `bw-cli-cache` の2つのボリュームをマウントしています。再起動後も `bw login` 状態を保持したい場合はこれらのボリュームを削除せずに運用し、キャッシュをリセットする場合は次を実行してください:

```bash
docker volume rm bw-cli-config bw-cli-cache
```

#### ステップ 4: Nginxの設定

`nginx/nginx.conf` を作成します :

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

    # HTTPからHTTPSへのリダイレクト
    server {
        listen 80;
        server_name yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    # フロントエンド
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

    # バックエンドAPI
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

        # ログストリーミングのためのWebSocketサポート
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

#### ステップ 5: SSL証明書の取得

CertbotとLet's Encryptを使用：

```bash
# Certbotのインストール
sudo apt install certbot

# 証明書の取得
sudo certbot certonly --standalone -d yourdomain.com -d api.yourdomain.com

# 証明書をnginxディレクトリにコピー
sudo mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/
sudo chmod 644 nginx/ssl/*.pem
```

#### ステップ 6: デプロイ

```bash
# サービスのビルドと起動
docker compose -f docker-compose.prod.yml up -d

# ステータス確認
docker compose -f docker-compose.prod.yml ps

# ログ表示
docker compose -f docker-compose.prod.yml logs -f
```

#### ステップ 7: SSL自動更新の設定

```bash
# 証明書更新のcronジョブ追加
sudo crontab -e

# 証明書を毎月更新する行を追加
0 0 1 * * certbot renew --quiet && docker compose -f /path/to/docker-compose.prod.yml restart nginx
```

### オプション 2: 個別のサービス

スケーラビリティ向上のため、フロントエンドとバックエンドを別々のサーバーにデプロイします。

#### バックエンドサーバー

```bash
# バックエンドサーバーにて
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# systemdサービスとしてインストール
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
# サービスの有効化と起動
sudo systemctl enable mcp-backend
sudo systemctl start mcp-backend
sudo systemctl status mcp-backend
```

#### フロントエンドサーバー

```bash
# フロントエンドサーバーにて
cd frontend
npm install
npm run build

# プロセス管理用PM2のインストール
npm install -g pm2

# PM2で起動
pm2 start npm --name "mcp-frontend" -- start
pm2 save
pm2 startup
```

### オプション 3: クラウドプラットフォーム

#### AWS デプロイメント

1. **ECS (Elastic Container Service) の使用**
   - フロントエンドとバックエンド用のECRリポジトリを作成
   - DockerイメージをECRにプッシュ
   - ECSタスク定義を作成
   - ECS Fargateへデプロイ

2. **EC2 の使用**
   - EC2インスタンスの起動（t3.medium以上）
   - Docker Composeデプロイ手順に従う
   - セキュリティグループの設定（ポート80, 443）
   - 静的IPアドレス用にElastic IPを使用

#### Google Cloud Platform

1. **Cloud Run の使用**
   - Google Container Registryへイメージをビルドしてプッシュ
   - フロントエンドとバックエンドを個別のCloud Runサービスとしてデプロイ
   - カスタムドメインの設定

2. **Compute Engine の使用**
   - VMインスタンスを作成
   - Docker Composeデプロイ手順に従う

#### DigitalOcean

1. **App Platform の使用**
   - GitHubリポジトリを接続
   - ビルド設定を行う
   - プッシュ時に自動デプロイ

2. **Droplet の使用**
   - Dropletを作成（4GB RAM以上）
   - Docker Composeデプロイ手順に従う

## セキュリティ強化

### 1. ファイアウォール設定

```bash
# UFW (Ubuntu) を使用
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2. Dockerセキュリティ

```bash
# Dockerデーモンをルートレスモードで実行（オプション）
dockerd-rootless-setuptool.sh install

# コンテナリソースの制限
# docker-compose.prod.yml に追加:
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
```

### 3. アプリケーションセキュリティ

- 強固なセッションシークレットの使用
- レート制限の有効化
- リクエストバリデーションの実装
- 定期的なセキュリティアップデート

### 4. ネットワークセキュリティ

- 管理アクセスにVPNを使用
- 機密エンドポイントへのIPホワイトリスト実装
- DDoS保護の有効化（Cloudflare, AWS Shield）

## 監視とメンテナンス

### ヘルスチェック

```bash
# サービスヘルスの確認
curl https://api.yourdomain.com/health

# フロントエンドの確認
curl https://yourdomain.com
```

### ロギング

```bash
# バックエンドログの表示
docker compose -f docker-compose.prod.yml logs -f backend

# フロントエンドログの表示
docker compose -f docker-compose.prod.yml logs -f frontend

# nginxログの表示
tail -f nginx/logs/access.log
tail -f nginx/logs/error.log
```

### 監視ツール

以下との統合を検討してください：
- **Prometheus + Grafana**: メトリクスとダッシュボード
- **ELK Stack**: ログ収集と分析
- **Uptime Robot**: 稼働監視
- **Sentry**: エラー追跡

### アップデート

```bash
# 最新の変更を取得
git pull origin main

# リビルドと再起動
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 古いイメージのクリーンアップ
docker image prune -a
```

## バックアップと復旧

### バックアップ対象

1. **設定ファイル**
   - `.env` ファイル
   - `docker-compose.prod.yml`
   - `nginx.conf`

2. **アプリケーションデータ**
   - ゲートウェイ設定
   - セッションデータ（永続化している場合）

3. **SSL証明書**
   - `/etc/letsencrypt/`

### バックアップスクリプト

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/mcp-gateway"
DATE=$(date +%Y%m%d_%H%M%S)

# バックアップディレクトリ作成
mkdir -p $BACKUP_DIR

# 設定のバックアップ
tar -czf $BACKUP_DIR/config_$DATE.tar.gz \
  frontend/.env.local \
  backend/.env \
  docker-compose.prod.yml \
  nginx/ 

# データのバックアップ
tar -czf $BACKUP_DIR/data_$DATE.tar.gz \
  backend/data/ 

# 過去7日間のバックアップのみ保持
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "バックアップ完了: $DATE"
```

### 自動バックアップ

```bash
# crontabに追加
crontab -e

# 毎日午前2時にバックアップ
0 2 * * * /opt/mcp-gateway/backup.sh
```

### 復旧

```bash
# サービスの停止
docker compose -f docker-compose.prod.yml down

# 設定の復元
tar -xzf config_YYYYMMDD_HHMMSS.tar.gz

# データの復元
tar -xzf data_YYYYMMDD_HHMMSS.tar.gz

# サービスの再起動
docker compose -f docker-compose.prod.yml up -d
```

## トラブルシューティング

### サービスが起動しない

```bash
# ログ確認
docker compose -f docker-compose.prod.yml logs

# Dockerデーモン確認
sudo systemctl status docker

# ディスク容量確認
df -h
```

### SSL証明書の問題

```bash
# 証明書テスト
openssl s_client -connect yourdomain.com:443

# 手動更新
sudo certbot renew --force-renewal
```

### パフォーマンスの問題

```bash
# リソース使用率確認
docker stats

# システムリソース確認
htop

# Docker最適化
docker system prune -a
```

## サポート

追加のヘルプが必要な場合：
- アプリケーションログを確認
- [GitHub Issues](repository-url/issues)を確認
- [要件定義ドキュメント](.kiro/specs/docker-mcp-gateway-console/requirements.md)を参照
