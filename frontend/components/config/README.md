# Gateway Config Editor Components

This directory contains components for editing the Gateway configuration.

## Components

### ConfigForm
The main form component for editing Gateway configuration. Features:
- Version management
- Global settings editor with add/remove functionality
- Server configuration with full CRUD operations
- Real-time validation with error and warning display
- Support for Bitwarden reference notation in all value fields

### SecretReferenceInput
A specialized input component that supports Bitwarden reference notation (`{{ bw:item-id:field }}`).

Features:
- Visual indicator when a Bitwarden reference is detected
- Helpful tips for users
- Error state handling
- Automatic validation of reference format

## Usage

```tsx
import ConfigForm from '@/components/config/ConfigForm';
import { GatewayConfig } from '@/lib/types/config';

function MyPage() {
  const [config, setConfig] = useState<GatewayConfig>({
    version: '1.0',
    servers: [],
    global_settings: {},
  });

  const handleSave = async (newConfig: GatewayConfig) => {
    await saveGatewayConfig(newConfig);
  };

  return (
    <ConfigForm
      initialConfig={config}
      onSave={handleSave}
      onCancel={() => router.back()}
    />
  );
}
```

## Validation

The `configValidator` utility provides:
- Real-time validation of Gateway configuration
- Detection of duplicate server names and container IDs
- Validation of required fields
- Bitwarden reference notation parsing and validation

## API Integration

The config API client (`lib/api/config.ts`) provides:
- `fetchGatewayConfig()` - Load current configuration
- `saveGatewayConfig(config)` - Save configuration changes

## Requirements Satisfied

This implementation satisfies requirements:
- 5.1: Reading and displaying current configuration
- 5.2: Saving configuration changes with validation
- 5.3: Support for Bitwarden reference notation
- 5.4: Validation and error handling
- 5.5: Error handling for file write failures
