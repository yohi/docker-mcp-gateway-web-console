import fc from 'fast-check';
import { CatalogItem } from '../../lib/types/catalog';
import { mapCatalogItemToConfig } from '../../lib/utils/transformers';

describe('Property 10: Catalog Prefill', () => {
  it('should correctly map CatalogItem to ContainerConfig', () => {
    /**
     * **Feature: docker-mcp-gateway-console, Property 10: Catalog選択時の設定プレフィル**
     * 
     * For any CatalogItem, the system should prefill the container configuration with:
     * - name = item.id
     * - image = item.docker_image
     * - env = item.default_env
     */
    fc.assert(
      fc.property(
        fc.record({
          // Generate IDs that are valid Docker container names (alphanumeric, -, _, .)
          // We prefix with 'id-' to ensure it starts with alphanumeric
          id: fc.string({ minLength: 1 }).map(s => 'id-' + s.replace(/[^a-zA-Z0-9_.-]/g, '')),
          name: fc.string(),
          description: fc.string(),
          vendor: fc.string(),
          category: fc.string(),
          docker_image: fc.string({ minLength: 1 }),
          icon_url: fc.string(),
          default_env: fc.dictionary(fc.string(), fc.string()),
          required_envs: fc.array(fc.string()),
          required_secrets: fc.array(fc.string())
        }),
        (item) => {
          // Cast to CatalogItem since fast-check generates a plain object
          const catalogItem = item as CatalogItem;
          
          const config = mapCatalogItemToConfig(catalogItem);
          
          return (
            config.name === catalogItem.id &&
            config.image === catalogItem.docker_image &&
            JSON.stringify(config.env) === JSON.stringify(catalogItem.default_env)
          );
        }
      ),
      { numRuns: 100 }
    );
  });
});
