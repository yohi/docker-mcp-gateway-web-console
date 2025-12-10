// Catalog types

export interface CatalogItem {
  id: string;
  name: string;
  description: string;
  vendor: string;
  category: string;
  docker_image: string;
  icon_url: string;
  default_env: Record<string, string>;
  required_envs: string[];
  required_secrets: string[];
  required_scopes?: string[];
  jwks_url?: string;
  verify_signatures?: boolean;
  permit_unsigned?: string[];
  allowlist_hint?: string;
  allowlist_status?: 'allowed' | 'pending' | 'rejected';
}

export interface CatalogResponse {
  servers: CatalogItem[];
  total: number;
  cached: boolean;
}

export interface CatalogSearchParams {
  source?: string;
  q?: string;
  category?: string;
}
