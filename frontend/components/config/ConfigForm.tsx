'use client';

import { useState, useEffect } from 'react';
import { GatewayConfig, ServerConfig } from '@/lib/types/config';
import { validateGatewayConfig } from '@/lib/utils/configValidator';
import SecretReferenceInput from './SecretReferenceInput';

interface ConfigFormProps {
  initialConfig: GatewayConfig;
  onSave: (config: GatewayConfig) => Promise<void>;
  onCancel?: () => void;
}

export default function ConfigForm({ initialConfig, onSave, onCancel }: ConfigFormProps) {
  const [config, setConfig] = useState<GatewayConfig>(initialConfig);
  const [isSaving, setSaving] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);

  // Real-time validation
  useEffect(() => {
    const result = validateGatewayConfig(config);
    setValidationErrors(result.errors);
    setValidationWarnings(result.warnings);
  }, [config]);

  const handleVersionChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setConfig({ ...config, version: e.target.value });
  };

  const handleGlobalSettingChange = (key: string, value: string) => {
    setConfig({
      ...config,
      global_settings: {
        ...config.global_settings,
        [key]: value,
      },
    });
  };

  const handleAddGlobalSetting = () => {
    const key = prompt('Enter setting key:');
    if (key && key.trim()) {
      handleGlobalSettingChange(key.trim(), '');
    }
  };

  const handleRemoveGlobalSetting = (key: string) => {
    const newSettings = { ...config.global_settings };
    delete newSettings[key];
    setConfig({ ...config, global_settings: newSettings });
  };

  const handleServerChange = (index: number, field: keyof ServerConfig, value: any) => {
    const newServers = [...config.servers];
    newServers[index] = { ...newServers[index], [field]: value };
    setConfig({ ...config, servers: newServers });
  };

  const handleServerConfigChange = (serverIndex: number, key: string, value: string) => {
    const newServers = [...config.servers];
    newServers[serverIndex] = {
      ...newServers[serverIndex],
      config: {
        ...newServers[serverIndex].config,
        [key]: value,
      },
    };
    setConfig({ ...config, servers: newServers });
  };

  const handleAddServerConfig = (serverIndex: number) => {
    const key = prompt('Enter config key:');
    if (key && key.trim()) {
      handleServerConfigChange(serverIndex, key.trim(), '');
    }
  };

  const handleRemoveServerConfig = (serverIndex: number, key: string) => {
    const newServers = [...config.servers];
    const newConfig = { ...newServers[serverIndex].config };
    delete newConfig[key];
    newServers[serverIndex] = { ...newServers[serverIndex], config: newConfig };
    setConfig({ ...config, servers: newServers });
  };

  const handleAddServer = () => {
    const newServer: ServerConfig = {
      name: '',
      container_id: '',
      enabled: true,
      config: {},
    };
    setConfig({ ...config, servers: [...config.servers, newServer] });
  };

  const handleRemoveServer = (index: number) => {
    if (confirm('Are you sure you want to remove this server?')) {
      const newServers = config.servers.filter((_, i) => i !== index);
      setConfig({ ...config, servers: newServers });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const result = validateGatewayConfig(config);
    if (!result.valid) {
      alert('Please fix validation errors before saving');
      return;
    }

    setSaving(true);
    try {
      await onSave(config);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Validation Messages */}
      {validationErrors.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <h3 className="text-sm font-medium text-red-800 mb-2">Validation Errors:</h3>
          <ul className="list-disc list-inside text-sm text-red-700 space-y-1">
            {validationErrors.map((error, i) => (
              <li key={i}>{error}</li>
            ))}
          </ul>
        </div>
      )}

      {validationWarnings.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
          <h3 className="text-sm font-medium text-yellow-800 mb-2">Warnings:</h3>
          <ul className="list-disc list-inside text-sm text-yellow-700 space-y-1">
            {validationWarnings.map((warning, i) => (
              <li key={i}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Version */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Version
        </label>
        <input
          type="text"
          value={config.version}
          onChange={handleVersionChange}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="1.0"
        />
      </div>

      {/* Global Settings */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-medium text-gray-900">Global Settings</h3>
          <button
            type="button"
            onClick={handleAddGlobalSetting}
            className="px-3 py-1 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Add Setting
          </button>
        </div>
        <div className="space-y-2">
          {Object.entries(config.global_settings).map(([key, value]) => (
            <div key={key} className="flex gap-2 items-start">
              <div className="flex-1">
                <SecretReferenceInput
                  label={key}
                  value={String(value)}
                  onChange={(newValue) => handleGlobalSettingChange(key, newValue)}
                />
              </div>
              <button
                type="button"
                onClick={() => handleRemoveGlobalSetting(key)}
                className="mt-6 px-3 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700"
              >
                Remove
              </button>
            </div>
          ))}
          {Object.keys(config.global_settings).length === 0 && (
            <p className="text-sm text-gray-500 italic">No global settings configured</p>
          )}
        </div>
      </div>

      {/* Servers */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-medium text-gray-900">Servers</h3>
          <button
            type="button"
            onClick={handleAddServer}
            className="px-3 py-1 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Add Server
          </button>
        </div>
        <div className="space-y-4">
          {config.servers.map((server, serverIndex) => (
            <div key={serverIndex} className="border border-gray-300 rounded-md p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="font-medium text-gray-900">
                  Server {serverIndex + 1}
                </h4>
                <button
                  type="button"
                  onClick={() => handleRemoveServer(serverIndex)}
                  className="px-3 py-1 text-sm bg-red-600 text-white rounded-md hover:bg-red-700"
                >
                  Remove
                </button>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Name
                  </label>
                  <input
                    type="text"
                    value={server.name}
                    onChange={(e) => handleServerChange(serverIndex, 'name', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="my-mcp-server"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Container ID
                  </label>
                  <input
                    type="text"
                    value={server.container_id}
                    onChange={(e) => handleServerChange(serverIndex, 'container_id', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="abc123def456"
                  />
                </div>
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id={`enabled-${serverIndex}`}
                  checked={server.enabled}
                  onChange={(e) => handleServerChange(serverIndex, 'enabled', e.target.checked)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor={`enabled-${serverIndex}`} className="ml-2 text-sm text-gray-700">
                  Enabled
                </label>
              </div>

              {/* Server Config */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h5 className="text-sm font-medium text-gray-700">Server Configuration</h5>
                  <button
                    type="button"
                    onClick={() => handleAddServerConfig(serverIndex)}
                    className="px-2 py-1 text-xs bg-gray-600 text-white rounded-md hover:bg-gray-700"
                  >
                    Add Config
                  </button>
                </div>
                <div className="space-y-2">
                  {Object.entries(server.config).map(([key, value]) => (
                    <div key={key} className="flex gap-2 items-start">
                      <div className="flex-1">
                        <SecretReferenceInput
                          label={key}
                          value={String(value)}
                          onChange={(newValue) => handleServerConfigChange(serverIndex, key, newValue)}
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveServerConfig(serverIndex, key)}
                        className="mt-6 px-2 py-2 text-xs bg-red-600 text-white rounded-md hover:bg-red-700"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                  {Object.keys(server.config).length === 0 && (
                    <p className="text-xs text-gray-500 italic">No configuration</p>
                  )}
                </div>
              </div>
            </div>
          ))}
          {config.servers.length === 0 && (
            <p className="text-sm text-gray-500 italic">No servers configured</p>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 justify-end">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
        )}
        <button
          type="submit"
          disabled={isSaving || validationErrors.length > 0}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {isSaving ? 'Saving...' : 'Save Configuration'}
        </button>
      </div>
    </form>
  );
}
