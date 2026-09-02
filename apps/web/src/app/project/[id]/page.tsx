"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { api, type Project, type Clip, type ReclipInput } from "@/lib/api";
import Link from "next/link";
import toast from "react-hot-toast";

const STAGE_LABELS: Record<string, string> = {
  download: "Download",
  transcribe: "Transcribe",
  select: "AI Select",
  crop: "Crop & Encode",
  caption: "Caption",
};

const STAGE_ICONS: Record<string, string> = {
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
  transcribe: "M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8",
  select: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 14 18.469V19a2 2 0 1 1-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
  crop: "M6.13 1L6 16a2 2 0 0 0 2 2h15M1 6.13L16 6a2 2 0 0 1 2 2v15",
  caption: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
};

const STATUS_STYLES: Record<string, { bg: string; text: string; icon: string }> = {
  pending: { bg: "bg-zinc-800", text: "text-zinc-500", icon: "text-zinc-600" },
  running: { bg: "bg-primary/20", text: "text-primary", icon: "text-primary" },
  success: { bg: "bg-cf-success/20", text: "text-cf-success", icon: "text-cf-success" },
  failed: { bg: "bg-cf-error/20", text: "text-cf-error", icon: "text-cf-error" },
  retrying: { bg: "bg-cf-warn/20", text: "text-cf-warn", icon: "text-cf-warn" },
};

function PipelineStage({ stage, status, errorMessage }: { stage: string; status: string; errorMessage: string | null }) {
  const styles = STATUS_STYLES[status] || STATUS_STYLES.pending;
  const iconPath = STAGE_ICONS[stage] || "";

  return (
    <div className={`rounded-xl border border-border/50 p-4 transition-all ${status === "running" ? "ring-1 ring-primary/30 shadow-lg shadow-primary/5" : ""}`}>
      <div className="flex items-center gap-3">
        <div className={`h-10 w-10 rounded-lg ${styles.bg} flex items-center justify-center flex-shrink-0`}>
          {status === "running" ? (
            <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
          ) : status === "success" ? (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className={`h-4 w-4 ${styles.icon}`}>
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : status === "failed" ? (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className={`h-4 w-4 ${styles.icon}`}>
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={`h-4 w-4 ${styles.icon}`}>
              <path d={iconPath} />
            </svg>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className={`text-sm font-medium ${styles.text}`}>
            {STAGE_LABELS[stage] || stage}
          </p>
          <p className="text-[11px] text-cf-muted capitalize">{status}</p>
        </div>
      </div>
      {errorMessage && (
        <p className="mt-2 text-xs text-cf-error bg-cf-error/10 rounded-lg px-3 py-2 break-words">
          {errorMessage}
        </p>
      )}
    </div>
  );
}

function ClipCard({
  clip,
  onApprove,
  onReject,
}: {
  clip: Clip;
  onApprove: () => void;
  onReject: () => void;
}) {
  const duration = clip.end_sec - clip.start_sec;
  const normalizedFileUrl = clip.file_url ? clip.file_url.replace(/\\/g, "/") : "";
  const normalizedThumbUrl = clip.thumbnail_url ? clip.thumbnail_url.replace(/\\/g, "/") : "";
  const videoUrl = normalizedFileUrl ? (normalizedFileUrl.startsWith("media") ? `http://localhost:8000/${normalizedFileUrl}` : normalizedFileUrl) : "";
  const thumbUrl = normalizedThumbUrl ? (normalizedThumbUrl.startsWith("media") ? `http://localhost:8000/${normalizedThumbUrl}` : normalizedThumbUrl) : "";

  const handleRegenerateThumb = async () => {
    try {
      // In a real app we might ask for text overlay here
      await fetch(`http://localhost:8000/api/clips/${clip.id}/thumbnail`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: null, style: "minimal" }),
      });
      toast.success("Thumbnail regenerating...");
      // A quick reload to fetch new thumbnail
      setTimeout(() => window.location.reload(), 1500);
    } catch (e) {
      toast.error("Failed to regenerate thumbnail");
    }
  };

  return (
    <div className="rounded-xl bg-card border border-border/50 overflow-hidden transition-all hover:border-border flex flex-col">
      {/* Video Preview */}
      <div className="aspect-[9/16] bg-zinc-900 flex items-center justify-center relative group overflow-hidden">
        {clip.file_url ? (
          <>
            {clip.thumbnail_url ? (
              <video
                src={videoUrl}
                className="w-full h-full object-cover"
                controls
                poster={thumbUrl}
                preload="none"
              />
            ) : (
              <video
                src={videoUrl}
                className="w-full h-full object-cover"
                controls
                preload="none"
              />
            )}
            
            {/* Quick Actions Overlay */}
            <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <button 
                onClick={handleRegenerateThumb}
                className="bg-black/60 hover:bg-black/80 text-white p-1.5 rounded-md backdrop-blur-sm text-xs flex items-center gap-1 border border-white/10"
                title="Regenerate Thumbnail"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              </button>
            </div>

          </>
        ) : (
          <div className="text-cf-muted text-xs">Processing...</div>
        )}
      </div>

      {/* Info */}
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <span className="text-xs text-cf-muted">
            {clip.start_sec.toFixed(1)}s - {clip.end_sec.toFixed(1)}s ({duration.toFixed(0)}s)
          </span>
          <div className="flex items-center gap-1.5">
            {clip.transformation_score !== undefined && clip.transformation_score !== null && (
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                  clip.transformation_score >= 70
                    ? "bg-cf-success/15 text-cf-success border-cf-success/30"
                    : clip.transformation_score >= 40
                    ? "bg-primary/15 text-primary border-primary/30"
                    : "bg-cf-danger/15 text-cf-danger border-cf-danger/30"
                }`}
                title="Original Transformation Score (0-100)"
              >
                ✨ {clip.transformation_score}/100
              </span>
            )}
            {clip.score !== null && (
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                  clip.score >= 0.7
                    ? "bg-cf-accent/15 text-cf-accent border-cf-accent/30"
                    : clip.score >= 0.5
                    ? "bg-cf-warn/15 text-cf-warn border-cf-warn/30"
                    : "bg-cf-muted/15 text-cf-muted border-border"
                }`}
                title="Editorial Potential (Narrative & Hook Strength)"
              >
                🎯 {(clip.score * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </div>

        {clip.reasoning && (
          <p className="text-xs text-cf-muted leading-relaxed line-clamp-2">
            {clip.reasoning}
          </p>
        )}

        {/* Actions */}
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <button
              onClick={onApprove}
              disabled={clip.review_status === "approved"}
              className={`flex-1 rounded-lg px-3 py-2 text-xs font-medium transition-all ${
                clip.review_status === "approved"
                  ? "bg-cf-success/20 text-cf-success border border-cf-success/30"
                  : "bg-card border border-border hover:border-cf-success/50 hover:text-cf-success"
              }`}
            >
              {clip.review_status === "approved" ? "Approved" : "Approve"}
            </button>
            <button
              onClick={onReject}
              disabled={clip.review_status === "rejected"}
              className={`flex-1 rounded-lg px-3 py-2 text-xs font-medium transition-all ${
                clip.review_status === "rejected"
                  ? "bg-cf-error/20 text-cf-error border border-cf-error/30"
                  : "bg-card border border-border hover:border-cf-error/50 hover:text-cf-error"
              }`}
            >
              {clip.review_status === "rejected" ? "Rejected" : "Reject"}
            </button>
          </div>
          
          {/* Edit Studio & Download buttons */}
          <div className="flex gap-2">
            <Link
              href={`/project/${clip.project_id}/clip/${clip.id}`}
              className="flex-1 flex items-center justify-center gap-1 rounded-lg bg-background border border-border px-3 py-2 text-xs font-medium text-cf-muted hover:text-white hover:border-primary/50 transition-colors"
            >
              ✏️ Edit Clip
            </Link>
            {clip.file_url && clip.review_status === "approved" && (
              <a
                href={videoUrl}
                download={`clip-${clip.id}.mp4`}
                className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-primary/10 text-primary border border-primary/20 px-3 py-2 text-xs font-medium transition-all hover:bg-primary hover:text-primary-foreground"
                target="_blank"
                rel="noopener noreferrer"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                Download
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [showReclip, setShowReclip] = useState(false);
  const [reclipping, setReclipping] = useState(false);
  const [reclipSettings, setReclipSettings] = useState<ReclipInput>({
    clip_count: 5,
    min_length_sec: 20,
    max_length_sec: 60,
    aspect_ratio: "9:16",
    caption_style: "bold_karaoke",
    custom_prompt: "",
    time_range_start: null,
    time_range_end: null,
  });

  const fetchData = useCallback(async () => {
    try {
      const [proj, projClips] = await Promise.all([
        api.getProject(projectId),
        api.getProjectClips(projectId).catch(() => [] as Clip[]),
      ]);
      setProject(proj);
      setClips(projClips);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load project");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-refresh while pipeline is running
  useEffect(() => {
    if (!project) return;
    const isActive = !["done", "failed"].includes(project.status);
    if (!isActive) return;

    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [project, fetchData]);

  const handleReview = async (clipId: string, status: "approved" | "rejected") => {
    try {
      const updated = await api.updateClip(clipId, status);
      setClips((prev) => prev.map((c) => (c.id === clipId ? updated : c)));
    } catch (e: unknown) {
      console.error("Failed to update clip:", e);
      toast.error("Failed to update clip status");
    }
  };

  const [showExportModal, setShowExportModal] = useState(false);
  const [ackRights, setAckRights] = useState(false);
  const [ackNotClearance, setAckNotClearance] = useState(false);
  const [exportFolder, setExportFolder] = useState("C:\\ClipForgeExports");

  // Load configured export path from settings on mount
  useEffect(() => {
    api.getSettings().then((s) => {
      if (s.export_path) {
        setExportFolder(s.export_path);
      }
    }).catch(() => {});
  }, []);

  const handleExport = () => {
    if (clips.filter((c) => c.review_status === "approved").length === 0) {
      toast.error("No approved clips to export. Please approve at least one clip first.");
      return;
    }
    // Refresh export path from settings before opening
    api.getSettings().then((s) => {
      if (s.export_path) {
        setExportFolder(s.export_path);
      }
    }).catch(() => {});
    setShowExportModal(true);
  };

  const confirmExport = async () => {
    if (!ackRights || !ackNotClearance) {
      toast.error("Please acknowledge all rights policies before exporting.");
      return;
    }

    try {
      setExporting(true);
      const res = await api.exportProjectClips(projectId, exportFolder);
      toast.success(res.message || "Export completed successfully", { duration: 6000 });
      setShowExportModal(false);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to export clips");
    } finally {
      setExporting(false);
    }
  };

  const handleRetry = async () => {
    try {
      setRetrying(true);
      await api.retryProject(projectId);
      toast.success("Pipeline restarted successfully");
      fetchData();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to retry project");
    } finally {
      setRetrying(false);
    }
  };

  const handleReclip = async () => {
    try {
      setReclipping(true);
      await api.reclipProject(projectId, reclipSettings);
      toast.success("Generating more clips! Pipeline started.");
      setShowReclip(false);
      fetchData();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to start reclip");
    } finally {
      setReclipping(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col min-h-screen px-6 py-8">
        <div className="max-w-6xl mx-auto w-full space-y-8">
          <div className="h-24 w-full bg-cf-card border border-cf-border animate-pulse rounded-xl" />
          <div className="grid grid-cols-5 gap-3">
            {[1,2,3,4,5].map(i => <div key={i} className="h-20 bg-cf-card border border-cf-border animate-pulse rounded-xl" />)}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
             {[1,2,3,4].map(i => <div key={i} className="aspect-[9/16] bg-cf-card border border-cf-border animate-pulse rounded-xl" />)}
          </div>
        </div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-cf-error mb-4">{error || "Project not found"}</p>
          <Link href="/dashboard" className="text-primary text-sm hover:underline">
            Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const isActive = !["done", "failed"].includes(project.status);
  const stageOrder = ["download", "transcribe", "select", "crop", "caption"];

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center gap-4">
          <Link href="/dashboard" className="text-cf-muted hover:text-foreground transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </Link>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold tracking-tight truncate">
              {project.source_value.length > 50
                ? project.source_value.slice(0, 50) + "..."
                : project.source_value}
            </h1>
            <p className="text-xs text-cf-muted">
              Created {new Date(project.created_at).toLocaleDateString()}
            </p>
          </div>

          {/* Generate More button */}
          {project.status === "done" && (
            <button
              onClick={() => setShowReclip(!showReclip)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all active:scale-[0.97] flex items-center gap-1.5 ${
                showReclip
                  ? "bg-primary text-primary-foreground"
                  : "bg-cf-card border border-cf-border text-cf-muted-fg hover:bg-cf-card/80 hover:text-white"
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
              {showReclip ? "Close" : "✂️ Generate More"}
            </button>
          )}
          
          <Link
            href="/settings"
            className="rounded-lg bg-cf-card border border-cf-border px-3 py-1.5 text-xs font-medium text-cf-muted-fg transition-all hover:bg-cf-card/80 hover:text-white active:scale-[0.97] flex items-center gap-1.5"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
            LLM Settings
          </Link>
          <button
            onClick={handleExport}
            disabled={exporting || clips.filter(c => c.review_status === "approved").length === 0}
            className="rounded-lg bg-primary text-primary-foreground px-4 py-1.5 text-xs font-medium transition-all hover:bg-primary/90 active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          >
            {exporting ? (
              <div className="animate-spin h-3 w-3 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full" />
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            )}
            Export Approved ({clips.filter(c => c.review_status === "approved").length})
          </button>
          
          <button
            onClick={async () => {
              if (confirm("Are you sure you want to delete this project and all its clips?")) {
                try {
                  await api.deleteProject(projectId);
                  toast.success("Project deleted");
                  window.location.href = "/dashboard";
                } catch (e) {
                  toast.error("Failed to delete project");
                }
              }
            }}
            className="rounded-lg bg-cf-error/10 border border-cf-error/20 text-cf-error px-3 py-1.5 text-xs font-medium transition-all hover:bg-cf-error/20 active:scale-[0.97] flex items-center gap-1.5"
            title="Delete Project"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
          </button>

          {project.status === "failed" && (
            <button
              onClick={handleRetry}
              disabled={retrying}
              className="rounded-lg bg-cf-error text-white px-4 py-1.5 text-xs font-medium transition-all hover:bg-cf-error/90 active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              {retrying ? (
                <div className="animate-spin h-3 w-3 border-2 border-white/30 border-t-white rounded-full" />
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
              )}
              {retrying ? "Retrying..." : "Retry Pipeline"}
            </button>
          )}
          {isActive && (
            <div className="flex items-center gap-2 text-primary">
              <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
              <span className="text-sm font-medium capitalize">{project.status}...</span>
            </div>
          )}
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto px-6 py-8">
        <div className="max-w-6xl mx-auto space-y-8">
        
          {/* LLM Fallback Warning Banner */}
          {project.jobs.find(j => j.stage === "select" && j.error_message?.includes("LLM unavailable")) && (
            <div className="bg-cf-warn/10 border border-cf-warn/30 rounded-xl p-4 flex items-start gap-3">
              <div className="mt-0.5 text-cf-warn">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
              </div>
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-cf-warn">AI Selection Unavailable</h3>
                <p className="text-xs text-cf-muted mt-1 leading-relaxed">
                  The LLM couldn't be reached, so we fell back to evenly-spaced clips. To get intelligent, context-aware clips, please <Link href="/settings" className="text-cf-warn underline hover:text-white">check your LLM API settings</Link> and then click "Generate More Clips" below.
                </p>
              </div>
            </div>
          )}

          {/* Pipeline Progress */}
          <section>
            <h2 className="text-base font-semibold mb-4">Pipeline Progress</h2>
            <div className="grid grid-cols-5 gap-3">
              {stageOrder.map((stage) => {
                const job = project.jobs.find((j) => j.stage === stage);
                return (
                  <PipelineStage
                    key={stage}
                    stage={stage}
                    status={job?.status || "pending"}
                    errorMessage={job?.error_message || null}
                  />
                );
              })}
            </div>
          </section>

          {/* Reclip Settings Panel */}
          {showReclip && (
            <section className="rounded-xl bg-card border border-primary/30 p-6 space-y-5">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold flex items-center gap-2">
                  <span>✂️</span> Generate More Clips
                </h2>
                <p className="text-xs text-cf-muted">Skips download &amp; transcription — uses existing transcript</p>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="text-xs text-cf-muted block mb-1.5">Number of clips</label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={reclipSettings.clip_count}
                    onChange={(e) => setReclipSettings({ ...reclipSettings, clip_count: parseInt(e.target.value) || 5 })}
                    className="w-full rounded-lg bg-background border border-border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="text-xs text-cf-muted block mb-1.5">Min length (s)</label>
                  <input
                    type="number"
                    min={5}
                    max={300}
                    value={reclipSettings.min_length_sec}
                    onChange={(e) => setReclipSettings({ ...reclipSettings, min_length_sec: parseInt(e.target.value) || 20 })}
                    className="w-full rounded-lg bg-background border border-border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="text-xs text-cf-muted block mb-1.5">Max length (s)</label>
                  <input
                    type="number"
                    min={10}
                    max={600}
                    value={reclipSettings.max_length_sec}
                    onChange={(e) => setReclipSettings({ ...reclipSettings, max_length_sec: parseInt(e.target.value) || 60 })}
                    className="w-full rounded-lg bg-background border border-border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="text-xs text-cf-muted block mb-1.5">Aspect ratio</label>
                  <select
                    value={reclipSettings.aspect_ratio}
                    onChange={(e) => setReclipSettings({ ...reclipSettings, aspect_ratio: e.target.value })}
                    className="w-full rounded-lg bg-background border border-border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="9:16">9:16 (Shorts/Reels)</option>
                    <option value="1:1">1:1 (Square)</option>
                    <option value="16:9">16:9 (Landscape)</option>
                  </select>
                </div>
              </div>

              {/* Specific Moments */}
              <div>
                <label className="text-xs text-cf-muted block mb-1.5">Include specific moments</label>
                <input
                  type="text"
                  placeholder="Example: find all the moments when someone scored"
                  value={reclipSettings.custom_prompt ?? ""}
                  onChange={(e) => setReclipSettings({ ...reclipSettings, custom_prompt: e.target.value })}
                  className="w-full rounded-lg bg-background border border-border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* Caption Style */}
              <div>
                <label className="text-xs text-cf-muted block mb-1.5">Caption style</label>
                <div className="flex gap-2">
                  {["bold_karaoke", "minimal", "subtitle", "none"].map((style) => (
                    <button
                      key={style}
                      onClick={() => setReclipSettings({ ...reclipSettings, caption_style: style })}
                      className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                        reclipSettings.caption_style === style
                          ? "bg-primary text-primary-foreground"
                          : "bg-background border border-border text-cf-muted-fg hover:border-primary/50"
                      }`}
                    >
                      {style.replace("_", " ")}
                    </button>
                  ))}
                </div>
              </div>

              {/* Optional Time Range */}
              <div>
                <label className="text-xs text-cf-muted block mb-1.5">Focus on specific time range (optional)</label>
                <div className="flex gap-3 items-center">
                  <input
                    type="number"
                    min={0}
                    placeholder="Start (seconds)"
                    value={reclipSettings.time_range_start ?? ""}
                    onChange={(e) => setReclipSettings({ ...reclipSettings, time_range_start: e.target.value ? parseFloat(e.target.value) : null })}
                    className="w-40 rounded-lg bg-background border border-border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <span className="text-cf-muted text-xs">to</span>
                  <input
                    type="number"
                    min={0}
                    placeholder="End (seconds)"
                    value={reclipSettings.time_range_end ?? ""}
                    onChange={(e) => setReclipSettings({ ...reclipSettings, time_range_end: e.target.value ? parseFloat(e.target.value) : null })}
                    className="w-40 rounded-lg bg-background border border-border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <span className="text-cf-muted text-xs">Leave empty for full video</span>
                </div>
              </div>

              {/* Submit */}
              <button
                onClick={handleReclip}
                disabled={reclipping}
                className="w-full rounded-lg bg-primary text-primary-foreground py-2.5 text-sm font-semibold transition-all hover:bg-primary/90 active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {reclipping ? (
                  <>
                    <div className="animate-spin h-4 w-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full" />
                    Generating...
                  </>
                ) : (
                  <>
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                    Generate {reclipSettings.clip_count} More Clips
                  </>
                )}
              </button>
            </section>
          )}

          {/* Transformation Readiness Score & Warning Banner (context2-upgrade.md Section 2.4) */}
          {clips.length > 0 && (
            <section className="rounded-xl bg-card border border-border/60 p-5 space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-sm font-semibold">Transformation Readiness Score</h2>
                    <span
                      className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${
                        (clips.reduce((acc, c) => acc + (c.transformation_score || 50), 0) / clips.length) >= 70
                          ? "bg-cf-success/15 text-cf-success border-cf-success/30"
                          : (clips.reduce((acc, c) => acc + (c.transformation_score || 50), 0) / clips.length) >= 40
                          ? "bg-primary/15 text-primary border-primary/30"
                          : "bg-cf-danger/15 text-cf-danger border-cf-danger/30"
                      }`}
                    >
                      ✨ {Math.round(clips.reduce((acc, c) => acc + (c.transformation_score || 50), 0) / clips.length)}/100 Average
                    </span>
                  </div>
                  <p className="text-xs text-cf-muted">
                    Evaluated across 5 pillars: Exclusivity, Commentary Depth, Visual Reframing, Narrative Flow, and Editorial Callouts.
                  </p>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-cf-muted">Template:</span>
                  <span className="font-semibold text-primary capitalize px-2 py-0.5 rounded bg-primary/10 border border-primary/20">
                    {project.editorial_template || "explainer"}
                  </span>
                </div>
              </div>

              {/* Warning if any clip is in low transformation band */}
              {clips.some((c) => (c.transformation_score || 50) < 40) && (
                <div className="rounded-lg bg-cf-danger/10 border border-cf-danger/30 p-3 flex items-start gap-2.5">
                  <span className="text-cf-danger text-sm">⚠️</span>
                  <p className="text-xs text-cf-danger/90 leading-relaxed">
                    <strong>High Reuse Risk:</strong> Some generated clips have a low transformation score (&lt;40). Add original voiceover commentary, editorial callouts, or adjust the in/out crop before publishing.
                  </p>
                </div>
              )}
            </section>
          )}

          {/* Clips */}
          {clips.length > 0 && (
            <section>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold">Generated Clips &amp; Manifests</h2>
                <span className="text-xs text-cf-muted">
                  {clips.filter((c) => c.review_status === "approved").length} approved ·{" "}
                  {clips.filter((c) => c.review_status === "rejected").length} rejected ·{" "}
                  {clips.filter((c) => c.review_status === "pending").length} pending
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {clips.map((clip) => (
                  <ClipCard
                    key={clip.id}
                    clip={clip}
                    onApprove={() => handleReview(clip.id, "approved")}
                    onReject={() => handleReview(clip.id, "rejected")}
                  />
                ))}
              </div>
            </section>
          )}

          {/* No clips yet */}
          {clips.length === 0 && project.status !== "failed" && (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
              {isActive ? (
                <>
                  <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
                  <p className="text-cf-muted text-sm">Processing your video...</p>
                  <p className="text-cf-muted/60 text-xs">Clips will appear here once the pipeline completes</p>
                </>
              ) : (
                <p className="text-cf-muted text-sm">No clips generated</p>
              )}
            </div>
          )}
        </div>
      </main>

      {/* Pre-Export Rights Acknowledgement Modal (context2-upgrade.md Section 2.6) */}
      {showExportModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-card border border-border p-6 space-y-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            <div className="space-y-1.5">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <span>🛡️</span> Export Rights &amp; Policy Confirmation
              </h3>
              <p className="text-xs text-cf-muted leading-relaxed">
                Before exporting {clips.filter((c) => c.review_status === "approved").length} approved clips, please review and confirm your editorial rights declaration.
              </p>
            </div>

            <div className="space-y-3 rounded-xl bg-background border border-border/80 p-4">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={ackRights}
                  onChange={(e) => setAckRights(e.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary"
                />
                <span className="text-xs text-cf-foreground/90 leading-snug">
                  I declare that I possess valid rights, written license, authorized campaign consent, or legitimate transformative fair-use basis for this source material.
                </span>
              </label>

              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={ackNotClearance}
                  onChange={(e) => setAckNotClearance(e.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary"
                />
                <span className="text-xs text-cf-foreground/90 leading-snug">
                  I acknowledge that ClipForge outputs are editorial assists and do <strong>not</strong> guarantee copyright immunity, strike clearance, or YouTube Partner Program acceptance.
                </span>
              </label>
            </div>

            <div>
              <label className="block text-xs font-semibold text-cf-muted mb-1.5">
                Export Destination Folder
              </label>
              <input
                type="text"
                value={exportFolder}
                onChange={(e) => setExportFolder(e.target.value)}
                placeholder="e.g. D:\MyVideos\Exports"
                className="w-full rounded-lg bg-background border border-border px-3.5 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <p className="text-[11px] text-cf-muted mt-1.5 leading-relaxed">
                📁 A dedicated subfolder named after this project will be automatically created inside this destination, saving all approved MP4 video clips, thumbnails, and the export manifest JSON.
              </p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setShowExportModal(false)}
                className="rounded-lg px-4 py-2 text-xs font-medium text-cf-muted hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmExport}
                disabled={!ackRights || !ackNotClearance || exporting}
                className="rounded-lg bg-primary text-primary-foreground px-5 py-2 text-xs font-semibold transition-all hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {exporting ? (
                  <>
                    <div className="animate-spin h-3.5 w-3.5 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full" />
                    Exporting...
                  </>
                ) : (
                  "Confirm & Export Clips"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
