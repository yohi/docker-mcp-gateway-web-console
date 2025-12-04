// Catalog types

export interface CatalogItem {
  id: string;
  name: string;
  description: string;
  category: string;
  docker_image: string;
  default_env: Record<string, string>;
  required_secrets: string[];
}

export interface CatalogResponse {
  servers: CatalogItem[];
  total: number;
  cached: boolean;
}

export interface CatalogSearchParams {
  source: string;
  q?: string;
  category?: string;
}
