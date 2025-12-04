// Gateway configuration types

export interface ServerConfig {
  name: string;
  container_id: string;
  enabled: boolean;
  config: Record<string, any>;
}

export interface GatewayConfig {
  version: string;
  servers: ServerConfig[];
  global_settings: Record<string, any>;
}

export interface ConfigReadResponse {
  config: GatewayConfig;
}

export interface ConfigWriteRequest {
  config: GatewayConfig;
}

export interface ConfigWriteResponse {
  success: boolean;
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}
