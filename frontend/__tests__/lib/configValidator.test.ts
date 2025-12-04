import {
  validateGatewayConfig,
  isValidBitwardenReference,
  parseBitwardenReference,
} from '@/lib/utils/configValidator';
import { GatewayConfig } from '@/lib/types/config';

describe('configValidator', () => {
  describe('validateGatewayConfig', () => {
    it('validates a valid config', () => {
      const config: GatewayConfig = {
        version: '1.0',
        servers: [
          {
            name: 'test-server',
            container_id: 'abc123',
            enabled: true,
            config: {},
          },
        ],
        global_settings: {},
      };

      const result = validateGatewayConfig(config);
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('detects missing version', () => {
      const config: GatewayConfig = {
        version: '',
        servers: [],
        global_settings: {},
      };

      const result = validateGatewayConfig(config);
      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Version is required');
    });

    it('detects missing server name', () => {
      const config: GatewayConfig = {
        version: '1.0',
        servers: [
          {
            name: '',
            container_id: 'abc123',
            enabled: true,
            config: {},
          },
        ],
        global_settings: {},
      };

      const result = validateGatewayConfig(config);
      expect(result.valid).toBe(false);
      expect(result.errors.some(e => e.includes('Name is required'))).toBe(true);
    });

    it('detects duplicate server names', () => {
      const config: GatewayConfig = {
        version: '1.0',
        servers: [
          {
            name: 'duplicate',
            container_id: 'abc123',
            enabled: true,
            config: {},
          },
          {
            name: 'duplicate',
            container_id: 'def456',
            enabled: true,
            config: {},
          },
        ],
        global_settings: {},
      };

      const result = validateGatewayConfig(config);
      expect(result.valid).toBe(false);
      expect(result.errors.some(e => e.includes('Duplicate server names'))).toBe(true);
    });

    it('warns about disabled servers', () => {
      const config: GatewayConfig = {
        version: '1.0',
        servers: [
          {
            name: 'test-server',
            container_id: 'abc123',
            enabled: false,
            config: {},
          },
        ],
        global_settings: {},
      };

      const result = validateGatewayConfig(config);
      expect(result.valid).toBe(true);
      expect(result.warnings.some(w => w.includes('disabled'))).toBe(true);
    });
  });

  describe('isValidBitwardenReference', () => {
    it('validates correct Bitwarden reference', () => {
      expect(isValidBitwardenReference('{{ bw:item123:password }}')).toBe(true);
      expect(isValidBitwardenReference('{{ bw:abc-def:api_key }}')).toBe(true);
    });

    it('rejects invalid references', () => {
      expect(isValidBitwardenReference('regular value')).toBe(false);
      expect(isValidBitwardenReference('{{ bw:item123 }}')).toBe(false);
      expect(isValidBitwardenReference('bw:item123:password')).toBe(false);
      expect(isValidBitwardenReference('{{ item123:password }}')).toBe(false);
    });
  });

  describe('parseBitwardenReference', () => {
    it('parses valid reference', () => {
      const result = parseBitwardenReference('{{ bw:item123:password }}');
      expect(result).toEqual({
        itemId: 'item123',
        field: 'password',
      });
    });

    it('handles whitespace', () => {
      const result = parseBitwardenReference('{{  bw:item123:password  }}');
      expect(result).toEqual({
        itemId: 'item123',
        field: 'password',
      });
    });

    it('returns null for invalid reference', () => {
      expect(parseBitwardenReference('invalid')).toBeNull();
      expect(parseBitwardenReference('{{ bw:item123 }}')).toBeNull();
    });
  });
});
