// Inspector types for MCP protocol communication

export interface ToolInfo {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

export interface ResourceInfo {
  uri: string;
  name: string;
  description: string;
  mime_type?: string;
}

export interface PromptArgument {
  name: string;
  description?: string;
  required?: boolean;
}

export interface PromptInfo {
  name: string;
  description: string;
  arguments: PromptArgument[];
}

export interface InspectorResponse {
  tools: ToolInfo[];
  resources: ResourceInfo[];
  prompts: PromptInfo[];
}
