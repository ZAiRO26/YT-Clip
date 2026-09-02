/**
 * ClipForge AI — API Client
 *
 * Typed fetch wrapper for all backend endpoints.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface LLMSettings {
  llm_base_url: string;
  llm_api_key: string;
  llm_model: string;
  export_path?: string;
}

export interface CampaignBrief {
  id: string;
  owner_id: string;
  name: string;
  brief_json: Record<string, unknown>;
  created_at: string;
}

export interface JobStatus {
  id: string;
  stage: string;
  status: string;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
}

export interface Project {
  id: string;
  owner_id: string;
  title?: string;
  source_type: string;
  source_value: string;
  rights_basis: string;
  rights_proof_url?: string | null;
  rights_notes?: string | null;
  source_risk_label: string;
  editorial_template: string;
  campaign_brief_id: string | null;
  clip_count: number;
  min_length_sec: number;
  max_length_sec: number;
  aspect_ratio: string;
  crop_mode?: string;
  caption_style: string;
  default_effects?: Array<{ id: string; intensity?: number }>;
  default_voice_id?: string;
  status: string;
  created_at: string;
  jobs: JobStatus[];
}

export interface ProjectListItem {
  id: string;
  title?: string;
  source_type: string;
  source_value: string;
  rights_basis: string;
  source_risk_label: string;
  editorial_template: string;
  clip_count: number;
  status: string;
  created_at: string;
  preview_url: string | null;
}

export interface Clip {
  id: string;
  project_id: string;
  start_sec: number;
  end_sec: number;
  score: number | null;
  transformation_score?: number | null;
  transformation_breakdown?: Record<string, number> | null;
  reasoning: string | null;
  file_url: string | null;
  thumbnail_url: string | null;
  render_manifest?: Record<string, unknown> | null;
  review_status: string;
  created_at: string;
}

export interface CreateProjectInput {
  title?: string;
  source_type: "youtube_url" | "local_folder" | "upload";
  source_value: string;
  rights_basis: string;
  rights_proof_url?: string | null;
  rights_notes?: string | null;
  editorial_template?: string;
  campaign_brief_id?: string | null;
  clip_count?: number;
  min_length_sec?: number;
  max_length_sec?: number;
  aspect_ratio?: string;
  crop_mode?: string;
  caption_style?: string;
  default_effects?: Array<{ id: string; intensity?: number }>;
  default_voice_id?: string;
  custom_prompt?: string | null;
  time_range_start?: number | null;
  time_range_end?: number | null;
}

export interface CreateBriefInput {
  name: string;
  brief_json: {
    tone?: string;
    required_mentions?: string[];
    banned_topics?: string[];
    brand_rules?: string;
  };
}

export interface ReclipInput {
  clip_count: number;
  min_length_sec: number;
  max_length_sec: number;
  aspect_ratio: string;
  caption_style: string;
  custom_prompt?: string | null;
  time_range_start?: number | null;
  time_range_end?: number | null;
}

class ApiClient {
  private base: string;

  constructor(base: string) {
    this.base = base;
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${this.base}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(error.detail || `API error: ${res.status}`);
    }

    return res.json();
  }

  // Health
  async health() {
    return this.request<Record<string, string>>("/health");
  }

  // Campaign Briefs
  async createBrief(data: CreateBriefInput) {
    return this.request<CampaignBrief>("/api/campaign-briefs", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async listBriefs() {
    return this.request<CampaignBrief[]>("/api/campaign-briefs");
  }

  // Projects
  async createProject(data: CreateProjectInput) {
    return this.request<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async listProjects() {
    return this.request<ProjectListItem[]>("/api/projects");
  }

  async getProject(id: string) {
    return this.request<Project>(`/api/projects/${id}`);
  }

  async deleteProject(id: string) {
    return this.request<{ message: string }>(`/api/projects/${id}`, {
      method: "DELETE",
    });
  }

  async getProjectClips(id: string) {
    return this.request<Clip[]>(`/api/projects/${id}/clips`);
  }

  // Clips
  async updateClip(id: string, reviewStatus: "pending" | "approved" | "rejected") {
    return this.request<Clip>(`/api/clips/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ review_status: reviewStatus }),
    });
  }

  async exportProjectClips(id: string, exportPath: string) {
    return this.request<{ message: string; detail?: string }>(`/api/projects/${id}/export`, {
      method: "POST",
      body: JSON.stringify({ export_path: exportPath }),
    });
  }

  async retryProject(id: string) {
    return this.request<{ message: string }>(`/api/projects/${id}/retry`, {
      method: "POST",
    });
  }

  // Reclip — generate more clips from existing project
  async reclipProject(id: string, data: ReclipInput) {
    return this.request<{ message: string; project_id: string; task_id: string }>(`/api/projects/${id}/reclip`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // Settings
  async getSettings() {
    return this.request<LLMSettings>("/api/settings");
  }

  async updateSettings(data: LLMSettings) {
    return this.request<LLMSettings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async testConnection(data: LLMSettings) {
    return this.request<{ status: string; message: string }>("/api/settings/test-connection", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }
}

export const api = new ApiClient(API_BASE);
