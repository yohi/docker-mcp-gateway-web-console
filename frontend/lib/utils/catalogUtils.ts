import type { CatalogItem } from '@/lib/types/catalog';

/**
 * Determines if a catalog item represents a remote server
 * @param item - The catalog item to check
 * @returns true if the item is a remote server, false otherwise
 */
export function isRemoteCatalogItem(item: CatalogItem): boolean {
  const hasDockerImage = Boolean(item.docker_image && item.docker_image.trim());
  if (item.is_remote || item.server_type === 'remote') return true;
  if (!hasDockerImage) return true; // docker イメージがなければリモート扱い
  return Boolean(item.remote_endpoint) && !hasDockerImage;
}

/**
 * Gets the remote endpoint URL for a catalog item
 * @param item - The catalog item
 * @returns The remote endpoint URL, or an empty string if not set
 */
export function getRemoteEndpoint(item: CatalogItem): string {
  return item.remote_endpoint || '';
}
