# OAuth セキュリティ対策

## SSRF (Server-Side Request Forgery) 対策

このアプリケーションは、OAuth認証フローにおいて以下のSSRF対策を実装しています。

### 1. HTTPSスキームの強制

すべてのOAuth URL（`authorize_url`, `token_url`, `redirect_uri`）はHTTPSスキームのみを許可します。HTTPスキームは拒否されます。

**設定**: backend/app/services/oauth.py の `_normalize_oauth_url` 関数

```python
if parsed.scheme != "https":
    raise OAuthError(f"{field_name} は HTTPS スキームである必要があります")
```

### 2. プライベート/ローカルIPの拒否

以下のIPアドレスへのアクセスは拒否されます：

- プライベートIPアドレス (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- ループバックアドレス (127.0.0.0/8, ::1)
- リンクローカルアドレス (169.254.0.0/16, fe80::/10)
- 予約済みアドレス
- クラウドメタデータエンドポイント (169.254.169.254)
- localhost, 127.0.0.1, ::1, 0.0.0.0

**設定**: backend/app/services/oauth.py の `_is_private_or_local_ip` および `_normalize_oauth_url` 関数

### 3. ドメイン許可リスト

OAuth URLのドメインは、設定された許可リストに含まれている必要があります。

**デフォルト動作**: 空文字列（すべてのドメインを拒否）

**セキュリティ原則**: 本番環境では必ず `OAUTH_ALLOWED_DOMAINS` を明示的に設定してください。未設定の場合、すべてのOAuth URLが拒否されます。

**環境変数設定**:
```bash
# カンマ区切りで複数のドメインを指定可能
OAUTH_ALLOWED_DOMAINS=github.com,gitlab.com,example.com

# 本番環境では必須
OAUTH_ALLOWED_DOMAINS=github.com
```

**設定ファイル**: backend/app/config.py
```python
oauth_allowed_domains: str = Field(
    default="", validation_alias="OAUTH_ALLOWED_DOMAINS"
)
```

### 4. ログ記録

すべての拒否された試行は警告ログに記録されます：

- 非HTTPSスキーム
- プライベート/ローカルIP
- メタデータエンドポイント
- 許可リスト外のドメイン

**ログ例**:
```
WARNING: OAuth URL rejected: non-HTTPS scheme. field=authorize_url url=http://example.com/auth
WARNING: OAuth URL rejected: private/local IP. field=token_url url=https://192.168.1.1/token ip=192.168.1.1
WARNING: OAuth URL rejected: domain not in allowlist. url=https://malicious.com/auth allowed_domains=['github.com']
```

### 5. DNS解決チェック

ホスト名がプライベートIPに解決されないことを確認します（DNS rebinding攻撃対策）。

## 運用推奨事項

### 本番環境の設定

1. **OAUTH_ALLOWED_DOMAINS を必ず設定（必須）**
   ```bash
   # 未設定の場合はすべてのOAuth URLが拒否されます
   OAUTH_ALLOWED_DOMAINS=github.com  # 必要なドメインのみを明示的に指定
   ```

2. **OAUTH_ALLOW_OVERRIDE は無効化**
   ```bash
   OAUTH_ALLOW_OVERRIDE=false  # デフォルト
   ```

3. **ログの監視**
   - OAuth URL拒否のログを定期的に確認
   - 異常なアクセス試行を検出

### テスト環境

テスト環境でもHTTPSを使用することを推奨しますが、localhostでのテストが必要な場合：

1. `redirect_uri` のみlocalhost許可を検討（慎重に）
2. テスト専用の設定ファイルを使用
3. 本番環境との設定の明確な分離

## セキュリティレビュー

このセキュリティ対策は以下の脅威モデルに対応しています：

- **SSRF攻撃**: 内部ネットワークへの不正アクセス
- **データ漏洩**: クラウドメタデータAPIへのアクセス
- **DNS rebinding**: DNSキャッシュポイズニング
- **中間者攻撃**: HTTPSの強制により軽減

## 参考資料

- [OWASP Server-Side Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [CWE-918: Server-Side Request Forgery (SSRF)](https://cwe.mitre.org/data/definitions/918.html)
