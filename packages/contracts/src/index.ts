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

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  llm_gateway?: string;
  database?: string;
  redis?: string;
}

export interface ReadyResponse {
  ready: boolean;
  checks: Record<string, boolean>;
}
