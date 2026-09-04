"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type CampaignBrief, type CreateProjectInput } from "@/lib/api";
import { RIGHTS_DECLARATIONS, type RightsBasis, type EditorialTemplate } from "@clipforge/contracts";
import Link from "next/link";

export default function NewProjectPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [briefs, setBriefs] = useState<CampaignBrief[]>([]);

  // Project Details
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState<"youtube_url" | "local_folder">("youtube_url");
  const [sourceValue, setSourceValue] = useState("");

  // Rights Declaration (Mandatory v2)
  const [rightsBasis, setRightsBasis] = useState<RightsBasis>("owned");
  const [rightsProofUrl, setRightsProofUrl] = useState("");
  const [rightsNotes, setRightsNotes] = useState("");

  // Editorial & Output Settings
  const [editorialTemplate, setEditorialTemplate] = useState<EditorialTemplate>("explainer");
  const [clipCount, setClipCount] = useState(5);
  const [minLength, setMinLength] = useState(20);
  const [maxLength, setMaxLength] = useState(60);
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [cropMode, setCropMode] = useState("face_track");
  const [captionStyle, setCaptionStyle] = useState("bold_karaoke");
  const [selectedEffects, setSelectedEffects] = useState<string[]>([]);
  const [voiceId, setVoiceId] = useState("af_bella");
  const [defaultMusicTrack, setDefaultMusicTrack] = useState("none");
  const [selectedBriefId, setSelectedBriefId] = useState<string | "">("");

  // Time & Selection Customization
  const [customPrompt, setCustomPrompt] = useState("");
  const [timeRangeStart, setTimeRangeStart] = useState("");
  const [timeRangeEnd, setTimeRangeEnd] = useState("");
  const [temporalDistribution, setTemporalDistribution] = useState<"even_spread" | "focus_window" | "top_moments">("even_spread");
  const [contentFocus, setContentFocus] = useState<"balanced" | "contestant_primary" | "judges_primary">("balanced");
  const [windowStartMm, setWindowStartMm] = useState("");
  const [windowStartSs, setWindowStartSs] = useState("");
  const [windowEndMm, setWindowEndMm] = useState("");
  const [windowEndSs, setWindowEndSs] = useState("");

  const updateTimeWindow = (sMm: string, sSs: string, eMm: string, eSs: string) => {
    const sMin = parseFloat(sMm) || 0;
    const sSec = parseFloat(sSs) || 0;
    if (sMm !== "" || sSs !== "") {
      setTimeRangeStart((sMin * 60 + sSec).toString());
    } else {
      setTimeRangeStart("");
    }

    const eMin = parseFloat(eMm) || 0;
    const eSec = parseFloat(eSs) || 0;
    if (eMm !== "" || eSs !== "") {
      setTimeRangeEnd((eMin * 60 + eSec).toString());
    } else {
      setTimeRangeEnd("");
    }
  };
  const [selectionBadge, setSelectionBadge] = useState<{
    type: "file" | "folder";
    name: string;
    detail?: string;
  } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    setSelectionBadge({
      type: "file",
      name: file.name,
      detail: `${sizeMb} MB`,
    });
    // If user already had a path like D:\Videos\, update the filename
    if (sourceValue && (sourceValue.includes("\\") || sourceValue.includes("/"))) {
      const lastSlash = Math.max(sourceValue.lastIndexOf("\\"), sourceValue.lastIndexOf("/"));
      const dir = sourceValue.slice(0, lastSlash + 1);
      setSourceValue(dir + file.name);
    } else {
      setSourceValue(file.name);
    }
  };

  const handleFolderSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const firstFile = files[0];
    const relativePath = firstFile.webkitRelativePath || "";
    const folderName = relativePath.split("/")[0] || "Selected Folder";

    const videoExtensions = [".mp4", ".mkv", ".mov", ".webm", ".avi", ".ts"];
    let videoCount = 0;
    for (let i = 0; i < files.length; i++) {
      const name = files[i].name.toLowerCase();
      if (videoExtensions.some((ext) => name.endsWith(ext))) {
        videoCount++;
      }
    }

    setSelectionBadge({
      type: "folder",
      name: folderName,
      detail: `${videoCount} video${videoCount === 1 ? "" : "s"} found`,
    });

    if (sourceValue && (sourceValue.includes("\\") || sourceValue.includes("/"))) {
      const lastSlash = Math.max(sourceValue.lastIndexOf("\\"), sourceValue.lastIndexOf("/"));
      const dir = sourceValue.slice(0, lastSlash + 1);
      setSourceValue(dir + folderName);
    } else {
      setSourceValue(folderName);
    }
  };

  const toggleEffect = (effId: string) => {
    setSelectedEffects((prev) =>
      prev.includes(effId) ? prev.filter((e) => e !== effId) : [...prev, effId]
    );
  };

  // Brief Creation Form
  const [showBriefForm, setShowBriefForm] = useState(false);
  const [briefName, setBriefName] = useState("");
  const [briefTone, setBriefTone] = useState("");
  const [briefRequired, setBriefRequired] = useState("");
  const [briefBanned, setBriefBanned] = useState("");
  const [briefRules, setBriefRules] = useState("");

  useEffect(() => {
    api.listBriefs().then(setBriefs).catch(() => {});
  }, []);

  const handleCreateBrief = async () => {
    if (!briefName.trim()) return;
    try {
      const brief = await api.createBrief({
        name: briefName.trim(),
        brief_json: {
          tone: briefTone.trim() || undefined,
          required_mentions: briefRequired.trim() ? briefRequired.split(",").map((s) => s.trim()) : [],
          banned_topics: briefBanned.trim() ? briefBanned.split(",").map((s) => s.trim()) : [],
          brand_rules: briefRules.trim() || undefined,
        },
      });
      setBriefs([brief, ...briefs]);
      setSelectedBriefId(brief.id);
      setShowBriefForm(false);
      setBriefName("");
      setBriefTone("");
      setBriefRequired("");
      setBriefBanned("");
      setBriefRules("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create brief");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!sourceValue.trim()) {
      setError("Please enter a YouTube URL or local folder path");
      return;
    }

    if (!rightsBasis) {
      setError("Please select a rights basis declaration for this project");
      return;
    }

    if (minLength >= maxLength) {
      setError("Minimum length must be less than maximum length");
      return;
    }

    setSubmitting(true);

    try {
      const input: CreateProjectInput = {
        title: title.trim() || undefined,
        source_type: sourceType,
        source_value: sourceValue.trim(),
        rights_basis: rightsBasis,
        rights_proof_url: rightsProofUrl.trim() || undefined,
        rights_notes: rightsNotes.trim() || undefined,
        editorial_template: editorialTemplate,
        clip_count: clipCount,
        min_length_sec: minLength,
        max_length_sec: maxLength,
        aspect_ratio: aspectRatio,
        crop_mode: cropMode,
        caption_style: captionStyle,
        default_effects: selectedEffects.map((e) => ({ id: e, intensity: 0.5 })),
        default_voice_id: voiceId,
        default_music_track: defaultMusicTrack,
        temporal_distribution: temporalDistribution,
        content_focus: contentFocus,
      };

      if (customPrompt.trim()) {
        input.custom_prompt = customPrompt.trim();
      }
      if (timeRangeStart) {
        input.time_range_start = parseFloat(timeRangeStart);
      }
      if (timeRangeEnd) {
        input.time_range_end = parseFloat(timeRangeEnd);
      }
      if (selectedBriefId) {
        input.campaign_brief_id = selectedBriefId;
      }

      const project = await api.createProject(input);
      router.push(`/project/${project.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create project");
      setSubmitting(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="border-b border-border/60 bg-surface/50 backdrop-blur px-6 py-4 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-cf-muted hover:text-foreground transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
                <path d="M19 12H5M12 19l-7-7 7-7" />
              </svg>
            </Link>
            <div>
              <h1 className="text-lg font-bold tracking-tight">New Clipping Project</h1>
              <p className="text-xs text-cf-muted">Rights-aware editorial studio</p>
            </div>
          </div>
          <span className="text-[11px] px-2.5 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary font-medium">
            v2 Studio
          </span>
        </div>
      </header>

      {/* Form */}
      <main className="flex-1 px-6 py-8">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto space-y-8">
          {/* Policy Banner */}
          <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-xs text-cf-muted flex items-start gap-3">
            <div className="p-1 rounded-md bg-primary/20 text-primary mt-0.5">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <div className="space-y-1">
              <span className="font-semibold text-foreground">Transformation-Supporting Editorial Studio</span>
              <p>
                ClipForge helps you add original commentary, structured layouts, and clear narration. Every export requires verified rights declaration and human review.
              </p>
            </div>
          </div>

          {/* Project Title */}
          <section className="space-y-3">
            <label className="text-sm font-semibold">Project Title (Optional)</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. AI News Breakdown - Episode 4"
              className="w-full rounded-lg border border-border bg-card px-4 py-2.5 text-sm text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
            />
          </section>

          {/* Mandatory Rights Declaration */}
          <section className="space-y-4 rounded-xl border border-border bg-surface p-5">
            <div>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold flex items-center gap-2">
                  <span>1. Source Rights Basis</span>
                  <span className="text-[10px] uppercase font-bold text-cf-accent bg-cf-accent/10 px-2 py-0.5 rounded">
                    Mandatory
                  </span>
                </h2>
                <span className="text-xs text-cf-muted">Policy Section 2.2</span>
              </div>
              <p className="text-xs text-cf-muted mt-1">
                Select your rights basis for this source video to determine workflow readiness and compliance.
              </p>
            </div>

            <div className="grid gap-2.5">
              {RIGHTS_DECLARATIONS.map((decl) => {
                const isSelected = rightsBasis === decl.value;
                const badgeColor =
                  decl.risk === "lower_workflow_risk"
                    ? "bg-cf-success/15 text-cf-success border-cf-success/30"
                    : decl.risk === "needs_review"
                    ? "bg-cf-warning/15 text-cf-warning border-cf-warning/30"
                    : "bg-cf-danger/15 text-cf-danger border-cf-danger/30";

                const badgeText =
                  decl.risk === "lower_workflow_risk"
                    ? "Lower workflow risk"
                    : decl.risk === "needs_review"
                    ? "Needs review"
                    : "Unknown / High claim risk";

                return (
                  <button
                    key={decl.value}
                    type="button"
                    onClick={() => setRightsBasis(decl.value)}
                    className={`text-left rounded-lg border p-3.5 transition-all flex items-start justify-between gap-3 ${
                      isSelected
                        ? "border-primary bg-primary/10 ring-1 ring-primary/50"
                        : "border-border bg-card hover:border-border/80"
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className={`h-3 w-3 rounded-full border flex items-center justify-center ${isSelected ? "border-primary bg-primary" : "border-border"}`}>
                          {isSelected && <span className="h-1.5 w-1.5 rounded-full bg-white" />}
                        </span>
                        <span className="text-sm font-medium text-foreground">{decl.label}</span>
                      </div>
                      <p className="text-xs text-cf-muted pl-5">{decl.description}</p>
                    </div>
                    <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border whitespace-nowrap ${badgeColor}`}>
                      {badgeText}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Optional Proof URL & Notes */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
              <input
                type="text"
                value={rightsProofUrl}
                onChange={(e) => setRightsProofUrl(e.target.value)}
                placeholder="Permission link / campaign URL (optional)"
                className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none"
              />
              <input
                type="text"
                value={rightsNotes}
                onChange={(e) => setRightsNotes(e.target.value)}
                placeholder="License notes or rights contact (optional)"
                className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none"
              />
            </div>
          </section>

          {/* Editorial Template Selector */}
          <section className="space-y-4 rounded-xl border border-border bg-surface p-5">
            <div>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">2. Editorial Transformation Template</h2>
                <span className="text-xs text-cf-muted">Policy Section 2.5</span>
              </div>
              <p className="text-xs text-cf-muted mt-1">
                Guides AI to structure clips with original commentary, hooks, and callouts.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
              {[
                { id: "explainer", name: "Explainer", desc: "Hook → Source excerpt → Analysis narration → Key takeaway" },
                { id: "commentary", name: "Commentary", desc: "Thesis statement → Evidence moment → Callouts → Conclusion" },
                { id: "news_context", name: "News / Context", desc: "Context card → Source quote → 'Why it matters' voiceover" },
                { id: "reaction_pip", name: "Reaction / PiP", desc: "Creator reaction overlay → Source excerpt in split layout" },
                { id: "quote_breakdown", name: "Quote Breakdown", desc: "Key quote → Annotation & definitions → Original summary" },
                { id: "campaign_promotion", name: "Campaign Promo", desc: "Brand disclosure → Permitted source → Call to Action" },
              ].map((tpl) => (
                <button
                  key={tpl.id}
                  type="button"
                  onClick={() => setEditorialTemplate(tpl.id as EditorialTemplate)}
                  className={`text-left rounded-lg border p-3 transition-all space-y-1 ${
                    editorialTemplate === tpl.id
                      ? "border-primary bg-primary/10 ring-1 ring-primary/50"
                      : "border-border bg-card hover:border-border/80"
                  }`}
                >
                  <span className="text-xs font-semibold text-foreground block">{tpl.name}</span>
                  <span className="text-[11px] text-cf-muted leading-relaxed block">{tpl.desc}</span>
                </button>
              ))}
            </div>
          </section>

          {/* Source Input */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold">3. Source Media</h2>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setSourceType("youtube_url")}
                className={`flex-1 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all ${
                  sourceType === "youtube_url"
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-card text-cf-muted hover:border-border/80"
                }`}
              >
                YouTube URL
              </button>
              <button
                type="button"
                onClick={() => setSourceType("local_folder")}
                className={`flex-1 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all ${
                  sourceType === "local_folder"
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-card text-cf-muted hover:border-border/80"
                }`}
              >
                Local File / Folder
              </button>
            </div>

            {sourceType === "youtube_url" ? (
              <input
                type="text"
                value={sourceValue}
                onChange={(e) => setSourceValue(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                className="w-full rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
              />
            ) : (
              <div className="space-y-2">
                <div className="flex gap-2 items-center">
                  <input
                    type="text"
                    value={sourceValue}
                    onChange={(e) => setSourceValue(e.target.value)}
                    placeholder="D:\Videos\my-video.mp4"
                    className="flex-1 rounded-lg border border-border bg-card px-4 py-2.5 text-sm text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
                  />
                  {/* Hidden browser native file inputs */}
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileSelected}
                    accept="video/mp4,video/mkv,video/mov,video/webm,video/avi,video/*"
                    className="hidden"
                  />
                  <input
                    type="file"
                    ref={folderInputRef}
                    onChange={handleFolderSelected}
                    // @ts-expect-error webkitdirectory is standard in Chromium/Firefox
                    webkitdirectory=""
                    directory=""
                    className="hidden"
                  />

                  {/* 100% Browser-Native Action Buttons */}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-primary/40 bg-primary/15 hover:bg-primary/25 text-primary text-xs font-semibold transition-all whitespace-nowrap shadow-sm"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                      <line x1="12" y1="18" x2="12" y2="12" />
                      <line x1="9" y1="15" x2="15" y2="15" />
                    </svg>
                    Browse Video File...
                  </button>

                  <button
                    type="button"
                    onClick={() => folderInputRef.current?.click()}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-border bg-card hover:bg-surface text-cf-muted hover:text-foreground text-xs font-medium transition-all whitespace-nowrap"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
                      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                    </svg>
                    Browse Folder...
                  </button>
                </div>

                {selectionBadge && (
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-primary/10 border border-primary/20 text-primary text-xs font-medium">
                    {selectionBadge.type === "file" ? (
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4 shrink-0 text-cf-success">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                        <polyline points="22 4 12 14.01 9 11.01" />
                      </svg>
                    ) : (
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4 shrink-0 text-primary">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                      </svg>
                    )}
                    <span>
                      Selected {selectionBadge.type === "file" ? "Video File" : "Folder"}: <strong>{selectionBadge.name}</strong>
                      {selectionBadge.detail && <span className="text-cf-muted ml-2">({selectionBadge.detail})</span>}
                    </span>
                  </div>
                )}

                <p className="text-[11px] text-cf-muted flex items-center gap-1.5">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3 w-3 text-cf-success">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 14 14" />
                  </svg>
                  Click <strong>Browse Video File...</strong> to choose a single video, <strong>Browse Folder...</strong> to select a folder, or paste the file path directly.
                </p>
              </div>
            )}
          </section>

          {/* Output & Length Settings */}
          <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-semibold text-cf-muted">Clip Count</label>
              <input
                type="number"
                min={1}
                max={20}
                value={clipCount}
                onChange={(e) => setClipCount(parseInt(e.target.value) || 5)}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold text-cf-muted">Min Length (sec)</label>
              <input
                type="number"
                min={5}
                max={120}
                value={minLength}
                onChange={(e) => setMinLength(parseInt(e.target.value) || 20)}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold text-cf-muted">Max Length (sec)</label>
              <input
                type="number"
                min={10}
                max={300}
                value={maxLength}
                onChange={(e) => setMaxLength(parseInt(e.target.value) || 60)}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
              />
            </div>
          </section>

          {/* Section 4: Production & Brand Styling Kit */}
          <section className="space-y-4 rounded-xl border border-border bg-surface p-5">
            <div>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">4. Production &amp; Brand Styling Kit</h2>
                <span className="text-[10px] bg-primary/10 text-primary border border-primary/20 px-2 py-0.5 rounded font-mono">
                  Batch Default
                </span>
              </div>
              <p className="text-xs text-cf-muted mt-1">
                Configure styling baseline for all generated clips. You can still fine-tune individual clips in the Studio later.
              </p>
            </div>

            {/* 4A: Layout & Crop */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-cf-muted block">Framing &amp; Aspect Ratio</label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: "face_track", label: "👤 Face Track 9:16", desc: "Auto-centers speaker" },
                  { id: "blur_background", label: "🌁 Blurred BG", desc: "Ambient side-blur" },
                  { id: "center", label: "🔲 Center Crop", desc: "Fixed center 9:16" },
                ].map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setCropMode(m.id)}
                    className={`p-2.5 rounded-lg border text-left transition-all ${
                      cropMode === m.id
                        ? "border-primary bg-primary/10 ring-1 ring-primary/50 text-primary"
                        : "border-border bg-card text-cf-muted hover:border-border/80"
                    }`}
                  >
                    <span className="text-xs font-semibold block">{m.label}</span>
                    <span className="text-[10px] text-cf-muted block mt-0.5">{m.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* 4B: Caption Presets */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-cf-muted block">Subtitle Typography Preset</label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {[
                  { id: "bold_karaoke", label: "⚡ Bold Karaoke", desc: "Yellow bounce pop" },
                  { id: "minimal", label: "✨ Minimal White", desc: "Clean modern sans" },
                  { id: "clean_subtitle", label: "📺 Clean Subtitle", desc: "Classic black bar" },
                  { id: "none", label: "🚫 None", desc: "No burned-in text" },
                ].map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setCaptionStyle(c.id)}
                    className={`p-2.5 rounded-lg border text-left transition-all ${
                      captionStyle === c.id
                        ? "border-primary bg-primary/10 ring-1 ring-primary/50 text-primary"
                        : "border-border bg-card text-cf-muted hover:border-border/80"
                    }`}
                  >
                    <span className="text-xs font-semibold block">{c.label}</span>
                    <span className="text-[10px] text-cf-muted block mt-0.5">{c.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* 4C: Motion & Visual Effects */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-cf-muted">Default Motion &amp; Visual Effects (Stackable)</label>
                <span className="text-[10px] text-cf-muted">{selectedEffects.length} active</span>
              </div>

              {selectedEffects.length > 2 && (
                <div className="p-2 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[11px] leading-tight">
                  ⚠️ Stacking more than 2 effects may reduce visual clarity.
                </div>
              )}

              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {[
                  { id: "film_grain", label: "🎞️ Film Grain" },
                  { id: "vignette", label: "🎬 Vignette" },
                  { id: "zoom", label: "🔍 Push-In Zoom" },
                  { id: "camera_shake", label: "📳 Handheld Shake" },
                  { id: "rgb_split", label: "🌈 RGB Glitch" },
                  { id: "vhs_noise", label: "📼 VHS Retro" },
                ].map((eff) => {
                  const isSelected = selectedEffects.includes(eff.id);
                  return (
                    <button
                      key={eff.id}
                      type="button"
                      onClick={() => toggleEffect(eff.id)}
                      className={`p-2 rounded-lg border text-xs font-medium text-left transition-all ${
                        isSelected
                          ? "border-primary bg-primary/15 text-primary ring-1 ring-primary/50 shadow-sm"
                          : "border-border bg-card text-foreground hover:border-white/20"
                      }`}
                    >
                      {eff.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 4D: Studio Voice Persona */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-cf-muted">Default Studio Voice Persona</label>
                <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded">
                  ⚡ Offline Kokoro TTS
                </span>
              </div>
              <select
                value={voiceId}
                onChange={(e) => setVoiceId(e.target.value)}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
              >
                <option value="af_bella">Bella — Warm &amp; Engaging Explainer (US Female)</option>
                <option value="am_adam">Adam — Dynamic &amp; Authoritative Host (US Male)</option>
                <option value="bf_emma">Emma — Expressive Narrator (British Female)</option>
                <option value="bm_george">George — Deep &amp; Authoritative (British Male)</option>
                <option value="af_sarah">Sarah — Crisp &amp; Articulate (US Female)</option>
                <option value="am_michael">Michael — Deep &amp; Resonant (US Male)</option>
                <option value="af_nicole">Nicole — Soft &amp; Conversational (US Female)</option>
              </select>
            </div>

            {/* 4E: Ambient Background Music */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-cf-muted">Ambient Background Music Bed</label>
                <span className="text-[10px] bg-primary/10 text-primary border border-primary/20 px-2 py-0.5 rounded">
                  🎵 Sidechain Ducking (-12dB)
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {[
                  { id: "none", label: "🚫 No Music", desc: "Keep original audio clean" },
                  { id: "ambient_focus", label: "🧘 Ambient Focus", desc: "Subtle minimal harmony" },
                  { id: "lofi_beats", label: "☕ Chill Lo-Fi", desc: "Warm hip-hop groove" },
                  { id: "upbeat_tech", label: "⚡ Upbeat Tech", desc: "High energy & punchy" },
                  { id: "epic_cinematic", label: "🎬 Cinematic Tension", desc: "Dramatic orchestral build" },
                ].map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setDefaultMusicTrack(m.id)}
                    className={`p-2.5 rounded-lg border text-left transition-all ${
                      defaultMusicTrack === m.id
                        ? "border-primary bg-primary/10 ring-1 ring-primary/50 text-primary"
                        : "border-border bg-card text-cf-muted hover:border-border/80"
                    }`}
                  >
                    <span className="text-xs font-semibold block">{m.label}</span>
                    <span className="text-[10px] text-cf-muted block mt-0.5">{m.desc}</span>
                  </button>
                ))}
              </div>
            </div>
          </section>

          {/* Section 5: Timeline Window & Selection Strategy */}
          <section className="space-y-4 rounded-xl border border-border bg-surface p-5">
            <div>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">5. Timeline Window &amp; Selection Strategy</h2>
                <span className="text-[10px] bg-primary/10 text-primary border border-primary/20 px-2 py-0.5 rounded font-mono">
                  Smart Spread
                </span>
              </div>
              <p className="text-xs text-cf-muted mt-1">
                Control where across the show clips are drawn from, balance contestant acts vs judge banter, and guarantee clip duration.
              </p>
            </div>

            {/* 5A: Content Focus Mode */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-cf-muted block">Content Focus Mode</label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {[
                  {
                    id: "balanced",
                    label: "🎭 Balanced Mix",
                    desc: "Equal representation of contestant acts & judge banter",
                  },
                  {
                    id: "contestant_primary",
                    label: "🎤 Contestant Acts",
                    desc: "Focus on performances, setups, punchlines (≥70% contestant clips)",
                  },
                  {
                    id: "judges_primary",
                    label: "⚖️ Judges Reactions",
                    desc: "Focus on roasts, banter, facial reactions, commentary (≥70% judge clips)",
                  },
                ].map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setContentFocus(f.id as any)}
                    className={`p-3 rounded-lg border text-left transition-all ${
                      contentFocus === f.id
                        ? "border-primary bg-primary/10 ring-1 ring-primary/50 text-primary"
                        : "border-border bg-card text-cf-muted hover:border-border/80"
                    }`}
                  >
                    <span className="text-xs font-semibold block">{f.label}</span>
                    <span className="text-[10px] text-cf-muted block mt-0.5">{f.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* 5B: Timeline Distribution Strategy */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-cf-muted block">Timeline Distribution Strategy</label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {[
                  {
                    id: "even_spread",
                    label: "🌐 Dynamic Temporal Binning",
                    desc: "Spreads clips evenly across entire timeline into chronological acts",
                  },
                  {
                    id: "focus_window",
                    label: "🎯 Custom Time Window",
                    desc: "Extract clips strictly within a specific timeframe (e.g. 40:00 to 50:00)",
                  },
                  {
                    id: "top_moments",
                    label: "⚡ Top Moments Only",
                    desc: "Extracts highest scoring moments anywhere without temporal binning",
                  },
                ].map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setTemporalDistribution(s.id as any)}
                    className={`p-3 rounded-lg border text-left transition-all ${
                      temporalDistribution === s.id
                        ? "border-primary bg-primary/10 ring-1 ring-primary/50 text-primary"
                        : "border-border bg-card text-cf-muted hover:border-border/80"
                    }`}
                  >
                    <span className="text-xs font-semibold block">{s.label}</span>
                    <span className="text-[10px] text-cf-muted block mt-0.5">{s.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* 5C: Time Window Selector (shown when focus_window selected) */}
            {temporalDistribution === "focus_window" && (
              <div className="rounded-lg bg-card/50 border border-border p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground">Timeline Window (MM:SS)</span>
                  <span className="text-[10px] text-cf-muted">Clips will only be extracted between these timestamps</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="text-[11px] text-cf-muted block mb-1">Window Start (Min : Sec)</label>
                    <div className="flex items-center gap-1.5">
                      <input
                        type="number"
                        min="0"
                        placeholder="MM"
                        value={windowStartMm}
                        onChange={(e) => {
                          setWindowStartMm(e.target.value);
                          updateTimeWindow(e.target.value, windowStartSs, windowEndMm, windowEndSs);
                        }}
                        className="w-20 rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-foreground font-mono focus:border-primary focus:outline-none"
                      />
                      <span className="text-cf-muted font-bold">:</span>
                      <input
                        type="number"
                        min="0"
                        max="59"
                        placeholder="SS"
                        value={windowStartSs}
                        onChange={(e) => {
                          setWindowStartSs(e.target.value);
                          updateTimeWindow(windowStartMm, e.target.value, windowEndMm, windowEndSs);
                        }}
                        className="w-20 rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-foreground font-mono focus:border-primary focus:outline-none"
                      />
                      {timeRangeStart && (
                        <span className="text-[10px] text-cf-muted font-mono ml-2">({timeRangeStart}s)</span>
                      )}
                    </div>
                  </div>

                  <div>
                    <label className="text-[11px] text-cf-muted block mb-1">Window End (Min : Sec)</label>
                    <div className="flex items-center gap-1.5">
                      <input
                        type="number"
                        min="0"
                        placeholder="MM"
                        value={windowEndMm}
                        onChange={(e) => {
                          setWindowEndMm(e.target.value);
                          updateTimeWindow(windowStartMm, windowStartSs, e.target.value, windowEndSs);
                        }}
                        className="w-20 rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-foreground font-mono focus:border-primary focus:outline-none"
                      />
                      <span className="text-cf-muted font-bold">:</span>
                      <input
                        type="number"
                        min="0"
                        max="59"
                        placeholder="SS"
                        value={windowEndSs}
                        onChange={(e) => {
                          setWindowEndSs(e.target.value);
                          updateTimeWindow(windowStartMm, windowStartSs, windowEndMm, e.target.value);
                        }}
                        className="w-20 rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-foreground font-mono focus:border-primary focus:outline-none"
                      />
                      {timeRangeEnd && (
                        <span className="text-[10px] text-cf-muted font-mono ml-2">({timeRangeEnd}s)</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 5D: Hard Duration Cap Guarantee Badge */}
            <div className="rounded-lg bg-primary/5 border border-primary/20 p-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-base">🛡️</span>
                <div>
                  <span className="text-xs font-semibold text-primary block">Strict Hard Duration Guarantee</span>
                  <span className="text-[10px] text-cf-muted block">
                    Clips will never exceed {maxLength}s. Enforced via Whisper sentence-end &amp; scene-cut boundary snapping.
                  </span>
                </div>
              </div>
              <span className="text-[10px] bg-primary/20 text-primary px-2.5 py-1 rounded font-mono font-bold">
                ≤ {maxLength}s
              </span>
            </div>
          </section>

          {/* Campaign Briefs & Guidance */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">6. Campaign Brief &amp; Guidance (Optional)</h2>
              <button
                type="button"
                onClick={() => setShowBriefForm(!showBriefForm)}
                className="text-xs text-primary hover:underline font-medium"
              >
                {showBriefForm ? "Cancel" : "+ New Brief"}
              </button>
            </div>

            {showBriefForm && (
              <div className="rounded-xl bg-card border border-border p-4 space-y-2.5">
                <input
                  type="text"
                  placeholder="Brief name"
                  value={briefName}
                  onChange={(e) => setBriefName(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none"
                />
                <input
                  type="text"
                  placeholder="Tone (e.g. informative, high energy)"
                  value={briefTone}
                  onChange={(e) => setBriefTone(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none"
                />
                <button
                  type="button"
                  onClick={handleCreateBrief}
                  className="rounded-lg bg-primary/10 border border-primary/20 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20"
                >
                  Save Brief
                </button>
              </div>
            )}

            {briefs.length > 0 && (
              <select
                value={selectedBriefId}
                onChange={(e) => setSelectedBriefId(e.target.value)}
                className="w-full rounded-lg border border-border bg-card px-3 py-2.5 text-sm text-foreground focus:border-primary focus:outline-none"
              >
                <option value="">No brief (general content)</option>
                {briefs.map((brief) => (
                  <option key={brief.id} value={brief.id}>
                    {brief.name}
                  </option>
                ))}
              </select>
            )}
          </section>

          {/* Error Message */}
          {error && (
            <div className="rounded-lg bg-cf-danger/10 border border-cf-danger/20 p-3 text-cf-danger text-sm">
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-primary py-3.5 text-sm font-semibold text-primary-foreground transition-all hover:bg-primary/90 hover:shadow-xl hover:shadow-primary/25 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? (
              <span className="flex items-center justify-center gap-2">
                <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                Creating project & declaring rights...
              </span>
            ) : (
              "Create Project & Start Ingestion"
            )}
          </button>
        </form>
      </main>
    </div>
  );
}
