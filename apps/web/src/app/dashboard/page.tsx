"use client";

import { useEffect, useState } from "react";
import { api, type ProjectListItem } from "@/lib/api";
import Link from "next/link";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-cf-muted/20 text-cf-muted",
  downloading: "bg-blue-500/20 text-blue-400",
  transcribing: "bg-purple-500/20 text-purple-400",
  selecting: "bg-yellow-500/20 text-yellow-400",
  encoding: "bg-orange-500/20 text-orange-400",
  captioning: "bg-pink-500/20 text-pink-400",
  done: "bg-cf-success/20 text-cf-success",
  failed: "bg-cf-error/20 text-cf-error",
};

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || "bg-cf-muted/20 text-cf-muted";
  return (
    <span className={`px-2.5 py-1 rounded-full text-[11px] font-semibold uppercase tracking-wider ${color}`}>
      {status}
    </span>
  );
}

function timeAgo(dateStr: string): string {
  const now = new Date();
  const d = new Date(dateStr);
  const diff = Math.floor((now.getTime() - d.getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function DashboardPage() {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProjects = () => {
      api.listProjects()
        .then(setProjects)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    };

    fetchProjects();
    const interval = setInterval(fetchProjects, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-primary flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4.5 w-4.5 text-primary-foreground">
                <polygon points="23 7 16 12 23 17 23 7" />
                <rect width="15" height="14" x="1" y="5" rx="2" ry="2" />
              </svg>
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight">ClipForge AI</h1>
              <p className="text-xs text-cf-muted">Automated video clipping studio</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/settings"
              className="rounded-lg border border-border px-3.5 py-2 text-xs font-medium text-foreground transition-colors hover:bg-card flex items-center gap-1.5"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
              Settings
            </Link>
            <Link
              href="/new"
              className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition-all hover:bg-primary/90 hover:shadow-lg hover:shadow-primary/25 flex items-center gap-1.5"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="h-3.5 w-3.5">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              New Project
            </Link>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 px-6 py-8">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-xl font-semibold mb-6">Projects</h2>

          {loading && (
            <div className="flex items-center justify-center py-20">
              <div className="animate-spin h-6 w-6 border-2 border-primary border-t-transparent rounded-full" />
            </div>
          )}

          {error && (
            <div className="rounded-lg bg-cf-error/10 border border-cf-error/20 p-4 text-cf-error text-sm">
              Failed to load projects: {error}
            </div>
          )}

          {!loading && !error && projects.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 gap-4">
              <div className="h-16 w-16 rounded-2xl bg-card border border-border flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-8 w-8 text-cf-muted">
                  <polygon points="23 7 16 12 23 17 23 7" />
                  <rect width="15" height="14" x="1" y="5" rx="2" ry="2" />
                </svg>
              </div>
              <p className="text-cf-muted text-sm">No projects yet</p>
              <Link
                href="/new"
                className="rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-all hover:bg-primary/90 hover:shadow-lg hover:shadow-primary/25"
              >
                Create your first project
              </Link>
            </div>
          )}

          {!loading && projects.length > 0 && (
            <div className="grid gap-3">
              {projects.map((project) => (
                <Link
                  key={project.id}
                  href={`/project/${project.id}`}
                  className="group rounded-xl bg-card border border-border/50 p-5 transition-all hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 min-w-0">
                      <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0 overflow-hidden">
                        {(project as any).preview_url ? (
                          <img 
                            src={(project as any).preview_url.startsWith("media") ? `http://localhost:8000/${(project as any).preview_url.replace(/\\/g, "/")}` : (project as any).preview_url.replace(/\\/g, "/")} 
                            alt="Project thumbnail" 
                            className="w-full h-full object-cover" 
                          />
                        ) : project.source_type === "youtube_url" ? (
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-5 w-5 text-primary">
                            <circle cx="12" cy="12" r="10" />
                            <polygon points="10 8 16 12 10 16 10 8" fill="currentColor" />
                          </svg>
                        ) : (
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-5 w-5 text-primary">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                          </svg>
                        )}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
                          {project.source_value.length > 60
                            ? project.source_value.slice(0, 60) + "..."
                            : project.source_value}
                        </p>
                        <p className="text-xs text-cf-muted mt-0.5">
                          {project.clip_count} clips · {timeAgo(project.created_at)}
                        </p>
                        {project.status === "failed" && (project as any).error_message && (
                          <p className="text-xs text-cf-error mt-1 flex items-center gap-1.5 line-clamp-1">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5 flex-shrink-0">
                              <circle cx="12" cy="12" r="10" />
                              <line x1="12" y1="8" x2="12" y2="12" />
                              <line x1="12" y1="16" x2="12.01" y2="16" />
                            </svg>
                            {(project as any).error_message}
                          </p>
                        )}
                      </div>
                    </div>
                    <StatusBadge status={project.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
