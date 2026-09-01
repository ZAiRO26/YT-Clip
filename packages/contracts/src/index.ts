/**
 * ClipForge AI — Shared Contracts & Types (v2)
 */

export type RightsBasis =
  | "owned"
  | "written_permission"
  | "authorized_campaign"
  | "commentary_review"
  | "other_unconfirmed";

export type SourceRiskLabel =
  | "lower_workflow_risk"
  | "needs_review"
  | "high_claim_risk"
  | "unknown";

export type EditorialTemplate =
  | "explainer"
  | "commentary"
  | "news_context"
  | "reaction_pip"
  | "quote_breakdown"
  | "campaign_promotion";

export type PipelineStage =
  | "ingest"
  | "analyze"
  | "select"
  | "editorial"
  | "render"
  | "qa";

export type JobStatus =
  | "pending"
  | "running"
  | "retrying"
  | "succeeded"
  | "failed"
  | "skipped";

export interface RightsOption {
  value: RightsBasis;
  label: string;
  description: string;
  risk: SourceRiskLabel;
}

export const RIGHTS_DECLARATIONS: RightsOption[] = [
  {
    value: "owned",
    label: "I own this source content",
    description: "Original footage recorded by you or your organization.",
    risk: "lower_workflow_risk",
  },
  {
    value: "written_permission",
    label: "I have written permission / licence",
    description: "Explicit license or written consent from the rights holder.",
    risk: "lower_workflow_risk",
  },
  {
    value: "authorized_campaign",
    label: "Authorized clipping or campaign program",
    description: "Source provided through an affiliate, brand, or authorized bounty.",
    risk: "lower_workflow_risk",
  },
  {
    value: "commentary_review",
    label: "Creating commentary / criticism / review",
    description: "Transformative commentary subject to independent fair-use evaluation.",
    risk: "needs_review",
  },
  {
    value: "other_unconfirmed",
    label: "Other / not confirmed",
    description: "Unconfirmed rights basis. Requires manual acknowledgment before export.",
    risk: "unknown",
  },
];

export interface ProjectCreateInput {
  title?: string;
  source_type: "youtube_url" | "local_folder" | "upload";
  source_value: string;
  rights_basis: RightsBasis;
  rights_proof_url?: string;
  rights_notes?: string;
  editorial_template?: EditorialTemplate;
  campaign_brief_id?: string;
  clip_count?: number;
  min_length_sec?: number;
  max_length_sec?: number;
  aspect_ratio?: "9:16" | "1:1" | "16:9";
  caption_style?: string;
  custom_prompt?: string;
  time_range_start?: number;
  time_range_end?: number;
}

export interface ProjectDTO {
  id: string;
  owner_id: string;
  title?: string;
  source_type: string;
  source_value: string;
  rights_basis: RightsBasis;
  rights_proof_url?: string;
  rights_notes?: string;
  source_risk_label: SourceRiskLabel;
  editorial_template: EditorialTemplate;
  campaign_brief_id?: string;
  clip_count: number;
  min_length_sec: number;
  max_length_sec: number;
  aspect_ratio: string;
  caption_style: string;
  status: string;
  created_at: string;
  jobs: Array<{
    id: string;
    stage: string;
    status: string;
    error_message?: string;
  }>;
}
