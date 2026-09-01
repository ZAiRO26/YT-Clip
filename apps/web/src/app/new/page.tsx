"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type CampaignBrief, type CreateProjectInput } from "@/lib/api";
import Link from "next/link";

export default function NewProjectPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [briefs, setBriefs] = useState<CampaignBrief[]>([]);

  // Form state
  const [sourceType, setSourceType] = useState<"youtube_url" | "local_folder">("youtube_url");
  const [sourceValue, setSourceValue] = useState("");
  const [clipCount, setClipCount] = useState(5);
  const [minLength, setMinLength] = useState(20);
  const [maxLength, setMaxLength] = useState(60);
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [captionStyle, setCaptionStyle] = useState("bold_karaoke");
  const [selectedBriefId, setSelectedBriefId] = useState<string | "">("");
  
  // New features
  const [customPrompt, setCustomPrompt] = useState("");
  const [timeRangeStart, setTimeRangeStart] = useState("");
  const [timeRangeEnd, setTimeRangeEnd] = useState("");

  // Brief creation
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

    if (minLength >= maxLength) {
      setError("Minimum length must be less than maximum length");
      return;
    }

    setSubmitting(true);

    try {
      const input: CreateProjectInput = {
        source_type: sourceType,
        source_value: sourceValue.trim(),
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
    <div className="flex-1 flex flex-col min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center gap-4">
          <Link href="/dashboard" className="text-cf-muted hover:text-foreground transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </Link>
          <h1 className="text-lg font-bold tracking-tight">New Project</h1>
        </div>
      </header>

      {/* Form */}
      <main className="flex-1 px-6 py-8">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto space-y-8">
          {/* Source */}
          <section className="space-y-4">
            <h2 className="text-base font-semibold">Source Video</h2>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setSourceType("youtube_url")}
                className={`flex-1 rounded-lg border px-4 py-3 text-sm font-medium transition-all ${
                  sourceType === "youtube_url"
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-card text-cf-muted hover:border-border/80"
                }`}
              >
                <div className="flex items-center gap-2 justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4">
                    <circle cx="12" cy="12" r="10" />
                    <polygon points="10 8 16 12 10 16 10 8" fill="currentColor" />
                  </svg>
                  YouTube URL
                </div>
              </button>
              <button
                type="button"
                onClick={() => setSourceType("local_folder")}
                className={`flex-1 rounded-lg border px-4 py-3 text-sm font-medium transition-all ${
                  sourceType === "local_folder"
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-card text-cf-muted hover:border-border/80"
                }`}
              >
                <div className="flex items-center gap-2 justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                  </svg>
                  Local Folder
                </div>
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

          {/* Processing Timeframe */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold">Processing timeframe</h2>
              <span className="px-2 py-0.5 rounded-full bg-cf-success/10 text-cf-success text-[10px] font-bold uppercase tracking-wider">
                Credit saver
              </span>
            </div>
            <div className="flex items-center gap-4">
              <input
                type="number"
                placeholder="Start (seconds)"
                value={timeRangeStart}
                onChange={(e) => setTimeRangeStart(e.target.value)}
                className="w-full rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
              />
              <span className="text-cf-muted text-sm font-medium">to</span>
              <input
                type="number"
                placeholder="End (seconds)"
                value={timeRangeEnd}
                onChange={(e) => setTimeRangeEnd(e.target.value)}
                className="w-full rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all"
              />
            </div>
            <p className="text-xs text-cf-muted mt-2">Leave empty to process the full video.</p>
          </section>

          {/* Specific Moments */}
          <section className="space-y-4">
            <h2 className="text-base font-semibold">Include specific moments</h2>
            <textarea
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              placeholder="Example: find all the moments when someone scored"
              rows={3}
              className="w-full rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50 transition-all resize-y"
            />
          </section>

          {/* Clip Settings */}
          <section className="space-y-4">
            <h2 className="text-base font-semibold">Clip Settings</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs text-cf-muted mb-1.5">Number of clips</label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={clipCount}
                  onChange={(e) => setClipCount(Number(e.target.value))}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50"
                />
              </div>
              <div>
                <label className="block text-xs text-cf-muted mb-1.5">Min length (s)</label>
                <input
                  type="number"
                  min={5}
                  max={300}
                  value={minLength}
                  onChange={(e) => setMinLength(Number(e.target.value))}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50"
                />
              </div>
              <div>
                <label className="block text-xs text-cf-muted mb-1.5">Max length (s)</label>
                <input
                  type="number"
                  min={10}
                  max={600}
                  value={maxLength}
                  onChange={(e) => setMaxLength(Number(e.target.value))}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50"
                />
              </div>
              <div>
                <label className="block text-xs text-cf-muted mb-1.5">Aspect ratio</label>
                <select
                  value={aspectRatio}
                  onChange={(e) => setAspectRatio(e.target.value)}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50"
                >
                  <option value="9:16">9:16 (Shorts/Reels)</option>
                  <option value="1:1">1:1 (Square)</option>
                  <option value="16:9">16:9 (Landscape)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs text-cf-muted mb-2">Caption style</label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <button
                  type="button"
                  onClick={() => setCaptionStyle("none")}
                  className={`relative h-20 rounded-xl border flex flex-col items-center justify-center transition-all ${
                    captionStyle === "none"
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border bg-card hover:border-border/80"
                  }`}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-6 w-6 text-cf-muted mb-2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
                  </svg>
                  <span className="text-[10px] font-medium text-cf-muted">No caption</span>
                </button>

                <button
                  type="button"
                  onClick={() => setCaptionStyle("minimal")}
                  className={`relative h-20 rounded-xl border flex flex-col items-center justify-center transition-all ${
                    captionStyle === "minimal"
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border bg-card hover:border-border/80"
                  }`}
                >
                  <span className="text-white font-sans text-xs tracking-wide bg-black/40 px-2 py-0.5 rounded shadow-sm mb-2">Minimalist style</span>
                  <span className="text-[10px] font-medium text-white/90">Minimal</span>
                </button>

                <button
                  type="button"
                  onClick={() => setCaptionStyle("subtitle")}
                  className={`relative h-20 rounded-xl border flex flex-col items-center justify-center transition-all ${
                    captionStyle === "subtitle"
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border bg-[#2c2c2c] hover:brightness-110"
                  }`}
                >
                  <span className="text-white font-serif italic text-xs tracking-wider mb-2 drop-shadow-md">Classic subtitle</span>
                  <span className="text-[10px] font-medium text-white/80">Subtitle</span>
                </button>

                <button
                  type="button"
                  onClick={() => setCaptionStyle("bold_karaoke")}
                  className={`relative h-20 rounded-xl border flex flex-col items-center justify-center transition-all ${
                    captionStyle === "bold_karaoke"
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border bg-[#1a1a1a] hover:brightness-110"
                  }`}
                >
                  <div className="flex flex-col items-center leading-tight mb-2">
                    <span className="text-white font-black uppercase text-[10px]" style={{ textShadow: "1px 1px 0 #000, -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000" }}>BOLD</span>
                    <span className="text-[#00FF00] font-black uppercase text-[12px]" style={{ textShadow: "1.5px 1.5px 0 #000, -1.5px -1.5px 0 #000, 1.5px -1.5px 0 #000, -1.5px 1.5px 0 #000" }}>KARAOKE</span>
                  </div>
                  <span className="text-[10px] font-medium text-white/80">Karaoke (Viral)</span>
                </button>
              </div>
            </div>
          </section>

          {/* Campaign Brief */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold">Campaign Brief</h2>
              <button
                type="button"
                onClick={() => setShowBriefForm(!showBriefForm)}
                className="text-xs text-primary hover:text-primary/80 font-medium transition-colors"
              >
                {showBriefForm ? "Cancel" : "+ New Brief"}
              </button>
            </div>

            {showBriefForm && (
              <div className="rounded-xl bg-card border border-border p-5 space-y-3">
                <input
                  type="text"
                  placeholder="Brief name"
                  value={briefName}
                  onChange={(e) => setBriefName(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none"
                />
                <input
                  type="text"
                  placeholder="Tone (e.g. energetic, professional)"
                  value={briefTone}
                  onChange={(e) => setBriefTone(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none"
                />
                <input
                  type="text"
                  placeholder="Required mentions (comma separated)"
                  value={briefRequired}
                  onChange={(e) => setBriefRequired(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none"
                />
                <input
                  type="text"
                  placeholder="Banned topics (comma separated)"
                  value={briefBanned}
                  onChange={(e) => setBriefBanned(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none"
                />
                <textarea
                  placeholder="Brand rules / special instructions"
                  value={briefRules}
                  onChange={(e) => setBriefRules(e.target.value)}
                  rows={2}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-cf-muted/50 focus:border-primary focus:outline-none resize-none"
                />
                <button
                  type="button"
                  onClick={handleCreateBrief}
                  className="rounded-lg bg-primary/10 border border-primary/20 px-4 py-2 text-sm font-medium text-primary hover:bg-primary/20 transition-colors"
                >
                  Save Brief
                </button>
              </div>
            )}

            {briefs.length > 0 && (
              <select
                value={selectedBriefId}
                onChange={(e) => setSelectedBriefId(e.target.value)}
                className="w-full rounded-lg border border-border bg-card px-3 py-2.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50"
              >
                <option value="">No brief (general content)</option>
                {briefs.map((brief) => (
                  <option key={brief.id} value={brief.id}>
                    {brief.name}
                  </option>
                ))}
              </select>
            )}

            {briefs.length === 0 && !showBriefForm && (
              <p className="text-xs text-cf-muted">
                No campaign briefs saved. Create one to guide AI clip selection.
              </p>
            )}
          </section>

          {/* Error */}
          {error && (
            <div className="rounded-lg bg-cf-error/10 border border-cf-error/20 p-3 text-cf-error text-sm">
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-primary py-3.5 text-sm font-semibold text-primary-foreground transition-all hover:bg-primary/90 hover:shadow-xl hover:shadow-primary/25 disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.99]"
          >
            {submitting ? (
              <span className="flex items-center justify-center gap-2">
                <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                Creating project...
              </span>
            ) : (
              "Start Processing"
            )}
          </button>
        </form>
      </main>
    </div>
  );
}
