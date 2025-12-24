// Catalog types

// Structured error codes from backend (design.md specification)
export type CatalogErrorCode =
  | 'invalid_source'
  | 'rate_limited'
  | 'upstream_unavailable'
  | 'internal_error';

export interface CatalogErrorResponse {
  detail: string;
  error_code: CatalogErrorCode;
  retry_after_seconds?: number;
}

export interface CatalogItem {
  id: string;
  name: string;
  description: string;
  vendor: string;
  category: string;
  docker_image?: string;
  icon_url: string;
  default_env: Record<string, string>;
  required_envs: string[];
  required_secrets: string[];
  required_scopes?: string[];
  oauth_authorize_url?: string;
  oauth_token_url?: string;
  oauth_client_id?: string;
  oauth_redirect_uri?: string;
  jwks_url?: string;
  verify_signatures?: boolean;
  permit_unsigned?: string[];
  allowlist_hint?: string;
  allowlist_status?: 'allowed' | 'pending' | 'rejected';
  // Remote MCP specific fields
  remote_endpoint?: string;
  is_remote?: boolean;
  server_type?: 'docker' | 'remote' | string;
  oauth_config?: Record<string, unknown> | null;
}

export interface CatalogResponse {
  servers: CatalogItem[];
  total: number;
  page: number;
  page_size: number;
  cached: boolean;
  categories: string[];
  warning?: string;
}

export interface CatalogSearchParams {
  source?: string;
  q?: string;
  category?: string;
  page?: number;
  page_size?: number;
}
