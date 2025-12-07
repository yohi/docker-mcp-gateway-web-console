import { CatalogItem } from '../types/catalog';
import { ContainerConfig } from '../types/containers';

/**
 * Maps a CatalogItem to a partial ContainerConfig for prefilling the creation form.
 * 
 * @param item The catalog item to map
 * @returns Partial container configuration
 */
export function mapCatalogItemToConfig(item: CatalogItem): Partial<ContainerConfig> {
  return {
    name: item.id,
    image: item.docker_image,
    env: item.default_env,
  };
}
