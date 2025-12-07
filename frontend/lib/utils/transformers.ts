import { CatalogItem } from '../types/catalog';
import { ContainerConfig } from '../types/containers';

const DOCKER_NAME_REGEX = /^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/;

function sanitizeContainerName(name: string): string {
  if (DOCKER_NAME_REGEX.test(name)) {
    return name;
  }

  // Replace spaces with '-' and remove other disallowed characters
  let sanitized = name.replace(/\s+/g, '-').replace(/[^a-zA-Z0-9_.-]/g, '');

  // Ensure non-empty and safe fallback if everything was stripped
  if (!sanitized) {
    return 'c' + Math.random().toString(36).substring(2, 8);
  }

  // Ensure first char is alphanumeric
  if (!/^[a-zA-Z0-9]/.test(sanitized)) {
    sanitized = `c${sanitized}`;
  }

  return sanitized;
}

/**
 * Maps a CatalogItem to a partial ContainerConfig for prefilling the creation form.
 * 
 * @param item The catalog item to map
 * @returns Partial container configuration
 */
export function mapCatalogItemToConfig(item: CatalogItem): Partial<ContainerConfig> {
  return {
    name: sanitizeContainerName(item.id),
    image: item.docker_image,
    env: item.default_env,
  };
}
