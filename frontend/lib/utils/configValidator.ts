// Configuration validation utilities

import { GatewayConfig, ServerConfig, ValidationResult } from '../types/config';

/**
 * Validates a Gateway configuration and returns validation results.
 */
export function validateGatewayConfig(config: GatewayConfig): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Validate version
  if (!config.version || config.version.trim() === '') {
    errors.push('Version is required');
  }

  // Validate servers array
  if (!Array.isArray(config.servers)) {
    errors.push('Servers must be an array');
  } else {
    // Validate each server
    config.servers.forEach((server, index) => {
      const serverErrors = validateServerConfig(server, index);
      errors.push(...serverErrors);
    });

    // Check for duplicate server names
    const serverNames = config.servers.map(s => s.name);
    const duplicates = serverNames.filter((name, index) => serverNames.indexOf(name) !== index);
    if (duplicates.length > 0) {
      errors.push(`Duplicate server names found: ${[...new Set(duplicates)].join(', ')}`);
    }

    // Check for duplicate container IDs
    const containerIds = config.servers.map(s => s.container_id);
    const duplicateIds = containerIds.filter((id, index) => containerIds.indexOf(id) !== index);
    if (duplicateIds.length > 0) {
      errors.push(`Duplicate container IDs found: ${[...new Set(duplicateIds)].join(', ')}`);
    }

    // Warnings
    if (config.servers.length === 0) {
      warnings.push('No servers configured');
    }

    const disabledServers = config.servers.filter(s => !s.enabled);
    if (disabledServers.length > 0) {
      warnings.push(`${disabledServers.length} server(s) are disabled`);
    }
  }

  // Validate global_settings
  if (config.global_settings && typeof config.global_settings !== 'object') {
    errors.push('Global settings must be an object');
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

/**
 * Validates a single server configuration.
 */
function validateServerConfig(server: ServerConfig, index: number): string[] {
  const errors: string[] = [];
  const prefix = `Server ${index + 1}`;

  if (!server.name || server.name.trim() === '') {
    errors.push(`${prefix}: Name is required`);
  }

  if (!server.container_id || server.container_id.trim() === '') {
    errors.push(`${prefix}: Container ID is required`);
  }

  if (typeof server.enabled !== 'boolean') {
    errors.push(`${prefix}: Enabled must be a boolean`);
  }

  if (server.config && typeof server.config !== 'object') {
    errors.push(`${prefix}: Config must be an object`);
  }

  return errors;
}

/**
 * Shared regex pattern for Bitwarden reference validation.
 * Format: {{ bw:<item-ref>:<field> }}
 * - item-ref: UUID or search string (no colons or whitespace)
 * - field: field name (no closing braces or whitespace)
 */
const BITWARDEN_REFERENCE_PATTERN = /^\{\{\s*bw:([^\s:]+):([^\s}]+)\s*\}\}$/;

/**
 * Validates Bitwarden reference notation.
 */
export function isValidBitwardenReference(value: string): boolean {
  return BITWARDEN_REFERENCE_PATTERN.test(value);
}

/**
 * Parses a Bitwarden reference and returns the item ID and field.
 */
export function parseBitwardenReference(reference: string): { itemId: string; field: string } | null {
  const match = reference.match(BITWARDEN_REFERENCE_PATTERN);
  if (!match) {
    return null;
  }
  const itemId = match[1].trim();
  const field = match[2].trim();

  if (itemId === '' || field === '') {
    return null;
  }

  return { itemId, field };
}
