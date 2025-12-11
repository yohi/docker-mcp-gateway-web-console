export interface GitHubTokenStatus {
  configured: boolean;
  source?: string | null;
  updated_by?: string | null;
  updated_at?: string | null;
}

export interface GitHubItemSummary {
  id: string;
  name: string;
  fields: string[];
  type?: string | null;
}

export interface GitHubTokenSearchResponse {
  items: GitHubItemSummary[];
}

export interface GitHubTokenSaveResponse {
  success: boolean;
  status: GitHubTokenStatus;
}

export interface GitHubTokenDeleteResponse {
  success: boolean;
}

