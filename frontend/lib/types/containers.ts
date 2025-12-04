// Container types

export type ContainerStatus = "running" | "stopped" | "error";

export interface ContainerInfo {
  id: string;
  name: string;
  image: string;
  status: ContainerStatus;
  created_at: string;
  ports: Record<string, number>;
  labels: Record<string, string>;
}

export interface ContainerConfig {
  name: string;
  image: string;
  env: Record<string, string>;
  ports: Record<string, number>;
  volumes: Record<string, string>;
  labels: Record<string, string>;
  command?: string[];
  network_mode?: string;
}

export interface ContainerListResponse {
  containers: ContainerInfo[];
}

export interface ContainerCreateResponse {
  container_id: string;
  name: string;
  status: string;
}

export interface ContainerActionResponse {
  success: boolean;
  message: string;
  container_id?: string;
}

export interface LogEntry {
  timestamp: string;
  message: string;
  stream: "stdout" | "stderr";
}
