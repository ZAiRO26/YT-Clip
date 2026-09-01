"use client";

import { useEffect, useState } from "react";
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
  const [captionStyle, setCaptionStyle] = useState("bold_karaoke");
  const [selectedBriefId, setSelectedBriefId] = useState<string | "">("");

  // Time & Selection Customization
  const [customPrompt, setCustomPrompt] = useState("");
  const [timeRangeStart, setTimeRangeStart] = useState("");
  const [timeRangeEnd, setTimeRangeEnd] = useState("");

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
        caption_style: captionStyle,
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
            <input
              type="text"
              value={sourceValue}
              onChange={(e) => setSourceValue(e.target.value)}
              placeholder={
                sourceType === "youtube_url"
                  ? "https://www.youtube.com/watch?v=..."
                  : "D:\\Videos\\my-video.mp4"
              }
              className="w-full rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
            />
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

          {/* Campaign Briefs & Guidance */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">Campaign Brief & Guidance</h2>
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
