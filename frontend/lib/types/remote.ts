export enum RemoteServerStatus {
  UNREGISTERED = 'unregistered',
  REGISTERED = 'registered',
  AUTH_REQUIRED = 'auth_required',
  AUTHENTICATED = 'authenticated',
  DISABLED = 'disabled',
  ERROR = 'error',
}

export interface RemoteServer {
  server_id: string;
  catalog_item_id: string;
  name: string;
  endpoint: string;
  status: RemoteServerStatus;
  credential_key?: string | null;
  last_connected_at?: string | null;
  error_message?: string | null;
  created_at: string;
}
