"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import { api, VoiceoverContext } from "@/lib/api";

interface ClipDetail {
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
  render_manifest?: Record<string, any> | null;
  review_status: string;
}

export default function ClipEditorPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const clipId = params.clipId as string;
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const [clip, setClip] = useState<ClipDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [rerendering, setRerendering] = useState(false);

  // Editor form state
  const [startSec, setStartSec] = useState<number>(0);
  const [endSec, setEndSec] = useState<number>(30);
  const [captionStyle, setCaptionStyle] = useState<string>("bold_karaoke");
  const [cropMode, setCropMode] = useState<string>("face_track");
  const [voiceId, setVoiceId] = useState<string>("af_bella");
  const [voiceoverText, setVoiceoverText] = useState<string>("");
  const [musicTrack, setMusicTrack] = useState<string>("none");
  const [selectedEffects, setSelectedEffects] = useState<string[]>([]);
  const [viewMode, setViewMode] = useState<"preview" | "split">("preview");

  // Voiceover Auto-Draft Script State
  const [voiceoverContext, setVoiceoverContext] = useState<VoiceoverContext | null>(null);
  const [generatingScript, setGeneratingScript] = useState(false);
  const [scriptStyle, setScriptStyle] = useState<"hook_intro" | "explainer" | "hype_reaction" | "outro_cta">("hook_intro");
  const [voiceoverStartOffsetSec, setVoiceoverStartOffsetSec] = useState<number>(0.5);
  const [unverifiedWarning, setUnverifiedWarning] = useState<string | null>(null);
  const [flaggedWords, setFlaggedWords] = useState<string[]>([]);

  const fetchClip = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/projects/${projectId}/clips`);
      if (!res.ok) throw new Error("Failed to load clips");
      const clips: ClipDetail[] = await res.json();
      const found = clips.find((c) => c.id === clipId);
      if (found) {
        setClip(found);
        setStartSec(found.start_sec);
        setEndSec(found.end_sec);
        if (found.render_manifest?.music_track) {
          setMusicTrack(found.render_manifest.music_track);
        }
      }

      // Fetch voiceover context and silence gap intelligence
      try {
        const ctx = await api.getClipVoiceoverContext(clipId);
        setVoiceoverContext(ctx);
      } catch (err) {
        console.warn("Could not fetch voiceover context:", err);
      }
    } catch (e) {
      toast.error("Failed to load clip details");
    } finally {
      setLoading(false);
    }
  }, [projectId, clipId]);

  useEffect(() => {
    fetchClip();
  }, [fetchClip]);

  const [savingMetadata, setSavingMetadata] = useState(false);
  const [videoVersion, setVideoVersion] = useState(Date.now());
  const [audioPreviewUrl, setAudioPreviewUrl] = useState<string | null>(null);

  const handleSaveMetadata = async () => {
    try {
      setSavingMetadata(true);
      const res = await fetch(`${apiBase}/api/clips/${clipId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start_sec: startSec,
          end_sec: endSec,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to save metadata");
      }
      toast.success("Clip metadata saved successfully");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to save metadata");
    } finally {
      setSavingMetadata(false);
    }
  };

  const handleDownloadClip = () => {
    const downloadUrl = `${apiBase}/api/clips/${clipId}/download`;
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = `clip_${clipId}.mp4`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    toast.success("Download started");
  };

  const handleAutoDraftScript = async (style: "hook_intro" | "explainer" | "hype_reaction" | "outro_cta") => {
    try {
      setGeneratingScript(true);
      setScriptStyle(style);
      const res = await api.generateVoiceoverScript(clipId, style);
      setVoiceoverText(res.script);
      setVoiceoverStartOffsetSec(res.start_offset_sec);
      if ((res as any).audio_preview_url) {
        setAudioPreviewUrl((res as any).audio_preview_url);
      }
      if (res.has_unverified_claim && res.warning) {
        setUnverifiedWarning(res.warning);
        setFlaggedWords(res.flagged_words || []);
      } else {
        setUnverifiedWarning(null);
        setFlaggedWords([]);
      }
      toast.success(`Generated ${res.word_count}-word ${style.replace("_", " ")} script!`);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to generate script");
    } finally {
      setGeneratingScript(false);
    }
  };

  const handleRerender = async () => {
    try {
      setRerendering(true);
      const payload = {
        start_sec: startSec,
        end_sec: endSec,
        caption_style: captionStyle,
        crop_mode: cropMode,
        voice_id: voiceId,
        voiceover_text: voiceoverText,
        voiceover_style: scriptStyle,
        voiceover_start_offset_sec: voiceoverStartOffsetSec,
        music_track: musicTrack,
        effects: selectedEffects.map((e) => ({ id: e, intensity: 0.5 })),
      };

      const res = await fetch(`${apiBase}/api/clips/${clipId}/rerender`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Re-render failed (HTTP ${res.status})`);
      }
      const data = await res.json();
      toast.success("Clip re-rendered successfully!");
      setVideoVersion(Date.now());
      setClip((prev) => prev ? { ...prev, file_url: data.file_url, transformation_score: data.transformation_score } : null);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Re-render failed");
    } finally {
      setRerendering(false);
    }
  };

  const toggleEffect = (effId: string) => {
    setSelectedEffects((prev) =>
      prev.includes(effId) ? prev.filter((e) => e !== effId) : [...prev, effId]
    );
  };

  const videoUrl = clip?.file_url
    ? `${clip.file_url.startsWith("media") ? `${apiBase}/${clip.file_url}` : clip.file_url}?v=${videoVersion}`
    : "";

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-foreground">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!clip) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-background text-foreground">
        <p className="text-cf-muted">Clip not found</p>
        <Link href={`/project/${projectId}`} className="text-primary text-sm hover:underline">
          Return to Project
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-background text-foreground overflow-hidden">
      {/* Top Navbar */}
      <header className="h-14 border-b border-border px-6 flex items-center justify-between bg-card z-20 shrink-0">
        <div className="flex items-center gap-4">
          <Link
            href={`/project/${projectId}`}
            className="flex items-center gap-1.5 text-xs font-semibold text-cf-muted hover:text-foreground transition-colors"
          >
            ← Back to Project
          </Link>
          <div className="h-4 w-px bg-border" />
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm tracking-tight">
              {clip.reasoning ? clip.reasoning.split("—")[0].trim() : `Clip ${clip.id.slice(0, 8)}`}
            </span>
            <span className="text-xs text-cf-muted">
              ({startSec.toFixed(1)}s - {endSec.toFixed(1)}s)
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* View Mode Toggle */}
          <div className="flex items-center bg-secondary p-0.5 rounded-lg border border-border">
            <button
              onClick={() => setViewMode("preview")}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                viewMode === "preview" ? "bg-primary text-primary-foreground" : "text-cf-muted"
              }`}
            >
              Preview
            </button>
            <button
              onClick={() => setViewMode("split")}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                viewMode === "split" ? "bg-primary text-primary-foreground" : "text-cf-muted"
              }`}
            >
              Before / After
            </button>
          </div>

          {/* Action 1: Save Metadata without re-render */}
          <button
            onClick={handleSaveMetadata}
            disabled={savingMetadata || rerendering}
            className="bg-secondary text-secondary-foreground border border-border px-3 py-1.5 rounded-lg text-xs font-semibold hover:bg-secondary/80 disabled:opacity-50 flex items-center gap-1.5 transition-all"
          >
            {savingMetadata ? "Saving..." : "Save Metadata"}
          </button>

          {/* Action 2: Re-render Video with effects & audio */}
          <button
            onClick={handleRerender}
            disabled={rerendering || savingMetadata}
            className="bg-primary text-primary-foreground px-4 py-1.5 rounded-lg text-xs font-semibold hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1.5 shadow-sm transition-all"
          >
            {rerendering ? (
              <>
                <div className="animate-spin h-3.5 w-3.5 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full" />
                Rendering...
              </>
            ) : (
              "⚡ Re-render Video (New Effects / Audio)"
            )}
          </button>

          {/* Action 3: Direct Download */}
          {clip.file_url && (
            <button
              onClick={handleDownloadClip}
              className="bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 px-3 py-1.5 rounded-lg text-xs font-semibold hover:bg-emerald-600/30 flex items-center gap-1.5 transition-all"
            >
              ⬇️ Download Clip
            </button>
          )}
        </div>
      </header>

      {/* Main Studio Grid */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
        {/* Left / Center: Video Player */}
        <div className="lg:col-span-7 bg-zinc-950 flex items-center justify-center p-6 relative overflow-hidden border-r border-border">
          {viewMode === "preview" ? (
            <div className="h-full max-h-[750px] aspect-[9/16] bg-black rounded-2xl overflow-hidden shadow-2xl border border-white/10 relative">
              {videoUrl ? (
                <video key={videoVersion} src={videoUrl} controls autoPlay className="w-full h-full object-cover" />
              ) : (
                <div className="flex items-center justify-center h-full text-xs text-cf-muted">
                  No video preview available
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-4 h-full max-h-[750px]">
              {/* Before: Raw Landscape */}
              <div className="flex flex-col items-center gap-2">
                <span className="text-[11px] font-bold text-cf-muted uppercase tracking-wider">Original Source (16:9)</span>
                <div className="w-80 aspect-video bg-black rounded-xl overflow-hidden border border-border flex items-center justify-center">
                  <span className="text-xs text-cf-muted">Source Excerpt</span>
                </div>
              </div>
              {/* After: 9:16 Vertical */}
              <div className="flex flex-col items-center gap-2">
                <span className="text-[11px] font-bold text-primary uppercase tracking-wider">Transform (9:16)</span>
                <div className="h-full max-h-[600px] aspect-[9/16] bg-black rounded-xl overflow-hidden border border-primary/40 shadow-lg shadow-primary/10">
                  {videoUrl && <video key={videoVersion} src={videoUrl} controls autoPlay className="w-full h-full object-cover" />}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right: Controls & Studio Inspector */}
        <div className="lg:col-span-5 bg-card overflow-y-auto p-6 space-y-6">
          {/* Section 1: In/Out Trimming */}
          <section className="space-y-3">
            <h3 className="text-xs font-bold text-primary uppercase tracking-wider">1. Timeline Trimming</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-cf-muted block mb-1">Start Time (sec)</label>
                <input
                  type="number"
                  step="0.1"
                  value={startSec}
                  onChange={(e) => setStartSec(parseFloat(e.target.value) || 0)}
                  className="w-full rounded-lg bg-background border border-border px-3 py-2 text-xs"
                />
              </div>
              <div>
                <label className="text-xs text-cf-muted block mb-1">End Time (sec)</label>
                <input
                  type="number"
                  step="0.1"
                  value={endSec}
                  onChange={(e) => setEndSec(parseFloat(e.target.value) || 0)}
                  className="w-full rounded-lg bg-background border border-border px-3 py-2 text-xs"
                />
              </div>
            </div>
            <p className="text-[11px] text-cf-muted">Duration: {(endSec - startSec).toFixed(1)}s</p>
          </section>

          {/* Section 2: Layout & Framing */}
          <section className="space-y-3">
            <h3 className="text-xs font-bold text-primary uppercase tracking-wider">2. Layout &amp; Crop</h3>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: "face_track", label: "Face Track 9:16" },
                { id: "blur_background", label: "Blurred BG" },
                { id: "center", label: "Center Crop" },
              ].map((m) => (
                <button
                  key={m.id}
                  onClick={() => setCropMode(m.id)}
                  className={`p-2.5 rounded-lg border text-xs font-medium text-center transition-all ${
                    cropMode === m.id
                      ? "bg-primary/15 border-primary text-primary"
                      : "bg-background border-border text-cf-muted hover:border-white/20"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </section>

          {/* Section 3: Subtitles & Captions */}
          <section className="space-y-3">
            <h3 className="text-xs font-bold text-primary uppercase tracking-wider">3. Caption Presets</h3>
            <div className="grid grid-cols-2 gap-2">
              {[
                { id: "bold_karaoke", label: "⚡ Bold Karaoke", desc: "Yellow bounce highlight" },
                { id: "minimal", label: "✨ Minimal White", desc: "Clean typography" },
                { id: "clean_subtitle", label: "📺 Clean Subtitle", desc: "Standard black box" },
                { id: "none", label: "🚫 None", desc: "No burned-in text" },
              ].map((c) => (
                <button
                  key={c.id}
                  onClick={() => setCaptionStyle(c.id)}
                  className={`p-3 rounded-lg border text-left transition-all ${
                    captionStyle === c.id
                      ? "bg-primary/15 border-primary text-primary"
                      : "bg-background border-border text-cf-muted hover:border-white/20"
                  }`}
                >
                  <p className="text-xs font-semibold">{c.label}</p>
                  <p className="text-[10px] text-cf-muted mt-0.5">{c.desc}</p>
                </button>
              ))}
            </div>
          </section>

          {/* Section 4: Voiceover & Narration */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-primary uppercase tracking-wider">4. Voiceover &amp; TTS Narration</h3>
              <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded flex items-center gap-1">
                ⚡ Local Kokoro TTS
              </span>
            </div>

            {/* Auto-Draft Script Toolbar */}
            <div className="rounded-xl border border-primary/20 bg-primary/5 p-3 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  ✨ Auto-Draft Script
                </span>
                <span className="text-[10px] text-cf-muted">
                  Grounded strictly in transcript dialogue
                </span>
              </div>

              {/* 4 Style Pills */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                {[
                  {
                    id: "hook_intro",
                    label: "⚡ Hook Intro",
                    badge: "6–9 words",
                    desc: "First 3s punchy hook",
                    disabled: false,
                  },
                  {
                    id: "explainer",
                    label: "📖 Explainer",
                    badge: "15–20 words",
                    desc: "Context over pause gap",
                    disabled: voiceoverContext ? !voiceoverContext.has_qualifying_gap : false,
                    disabledReason: "Requires ≥3s pause",
                  },
                  {
                    id: "hype_reaction",
                    label: "🔥 Hype Reaction",
                    badge: "12–16 words",
                    desc: "Climax reaction overlay",
                    disabled: false,
                  },
                  {
                    id: "outro_cta",
                    label: "💬 Outro CTA",
                    badge: "8–11 words",
                    desc: "Closing CTA hook",
                    disabled: false,
                  },
                ].map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    disabled={s.disabled || generatingScript}
                    onClick={() => handleAutoDraftScript(s.id as any)}
                    className={`p-2 rounded-lg text-left transition-all border relative flex flex-col justify-between ${
                      s.disabled
                        ? "opacity-40 cursor-not-allowed bg-surface border-border text-cf-muted"
                        : scriptStyle === s.id && voiceoverText
                        ? "bg-primary/20 border-primary text-foreground shadow-sm shadow-primary/20"
                        : "bg-surface hover:bg-surface-raised border-border text-foreground hover:border-primary/40"
                    }`}
                  >
                    <div>
                      <div className="text-[11px] font-semibold leading-tight">{s.label}</div>
                      <div className="text-[9px] text-cf-muted mt-0.5">{s.badge}</div>
                    </div>
                    {s.disabled && s.disabledReason && (
                      <span className="text-[8px] text-amber-400 mt-1 block">
                        ⚠️ {s.disabledReason}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              {generatingScript && (
                <div className="flex items-center gap-2 text-xs text-primary animate-pulse py-1">
                  <div className="h-3 w-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  Generating script grounded in transcript snippet...
                </div>
              )}
            </div>

            {/* Side-by-Side: Source Transcript Snippet & Script Editor */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {/* Left Column: Source Transcript Snippet */}
              <div className="rounded-lg bg-surface/80 border border-border p-3 space-y-1.5 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between text-[11px] font-medium text-cf-muted">
                    <span className="flex items-center gap-1">💬 Source Transcript Snippet</span>
                    <span>[{startSec.toFixed(1)}s – {endSec.toFixed(1)}s]</span>
                  </div>
                  <div className="text-xs text-foreground/90 mt-1.5 italic bg-background/50 p-2.5 rounded border border-border/50 max-h-28 overflow-y-auto leading-relaxed">
                    {voiceoverContext?.transcript_snippet ? (
                      `“${voiceoverContext.transcript_snippet}”`
                    ) : (
                      <span className="text-cf-muted not-italic">
                        No dialogue recorded in this clip window (visual performance).
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center justify-between text-[10px] text-cf-muted pt-1 border-t border-border/40">
                  <span>
                    {voiceoverContext?.has_qualifying_gap
                      ? `🟢 Pause detected (${voiceoverContext.gaps[0]?.duration_sec}s)`
                      : "⚪ Continuous dialogue (No ≥3s gap)"}
                  </span>
                  <span>{voiceoverContext?.segments?.length || 0} segments</span>
                </div>
              </div>

              {/* Right Column: AI Script Editor */}
              <div className="space-y-1.5 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between text-[11px] font-medium text-cf-muted">
                    <div className="flex items-center gap-2">
                      <span>Drafted Voiceover Script</span>
                      {audioPreviewUrl && (
                        <button
                          type="button"
                          onClick={() => {
                            const audio = new Audio(`http://localhost:8000/${audioPreviewUrl}?t=${Date.now()}`);
                            audio.play();
                            toast.success("Playing Kokoro audio preview...");
                          }}
                          className="bg-primary/20 text-primary hover:bg-primary/30 border border-primary/30 px-2 py-0.5 rounded text-[10px] font-semibold flex items-center gap-1 transition"
                        >
                          ▶️ Listen to Preview
                        </button>
                      )}
                    </div>
                    <span className={`text-[10px] ${
                      voiceoverText.split(/\s+/).filter(Boolean).length > 20
                        ? "text-amber-400"
                        : "text-emerald-400"
                    }`}>
                      {voiceoverText.split(/\s+/).filter(Boolean).length} words · ~{(voiceoverText.split(/\s+/).filter(Boolean).length / 2.8).toFixed(1)}s
                    </span>
                  </div>
                  <textarea
                    value={voiceoverText}
                    onChange={(e) => {
                      setVoiceoverText(e.target.value);
                      if (unverifiedWarning) setUnverifiedWarning(null);
                    }}
                    rows={3}
                    placeholder="Enter original commentary to voice over with Kokoro (or use Auto-Draft above)..."
                    className="w-full rounded-lg bg-background border border-border p-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary leading-relaxed"
                  />
                </div>
                <div className="flex items-center justify-between text-[10px] text-cf-muted">
                  <span className="flex items-center gap-1">
                    📍 Audio placement starts at: <strong className="text-foreground">{voiceoverStartOffsetSec.toFixed(1)}s</strong>
                  </span>
                  <button
                    type="button"
                    onClick={() => setVoiceoverText("")}
                    className="text-[10px] text-cf-muted hover:text-foreground transition"
                  >
                    Clear
                  </button>
                </div>
              </div>
            </div>

            {/* Unverified Claim Warning Banner */}
            {unverifiedWarning && (
              <div className="rounded-lg bg-amber-500/10 border border-amber-500/30 p-2.5 flex items-start gap-2 text-xs text-amber-200">
                <span className="text-base leading-none">⚠️</span>
                <div>
                  <strong className="font-semibold block text-amber-300">Unverified Claim Warning</strong>
                  <span className="text-[11px] text-amber-200/90 leading-tight block mt-0.5">
                    {unverifiedWarning}
                  </span>
                </div>
              </div>
            )}

            {/* Voice Selector */}
            <div>
              <label className="text-xs text-cf-muted block mb-1">Studio Voice Persona</label>
              <select
                value={voiceId}
                onChange={(e) => setVoiceId(e.target.value)}
                className="w-full rounded-lg bg-background border border-border px-3 py-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="af_bella">Bella — Warm &amp; Engaging Explainer (US Female)</option>
                <option value="am_adam">Adam — Dynamic &amp; Authoritative Host (US Male)</option>
                <option value="bf_emma">Emma — Thoughtful News &amp; Commentary (UK Female)</option>
                <option value="bm_george">George — Documentary &amp; Storyteller (UK Male)</option>
                <option value="af_sarah">Sarah — Clear &amp; Polished Narrator (US Female)</option>
                <option value="am_michael">Michael — Conversational &amp; Podcast Host (US Male)</option>
                <option value="af_nicole">Nicole — Relaxed &amp; Natural Dialogue (US Female)</option>
              </select>
            </div>
          </section>

          {/* Section 5: Ambient Background Music */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-primary uppercase tracking-wider">5. Ambient Background Music</h3>
              <span className="text-[10px] bg-primary/10 text-primary border border-primary/20 px-2 py-0.5 rounded">
                🎵 Dynamic Ducking (-12dB)
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {[
                { id: "none", label: "🚫 No Music", desc: "Keep raw video audio" },
                { id: "ambient_focus", label: "🧘 Ambient Focus", desc: "Subtle minimal bed" },
                { id: "lofi_beats", label: "☕ Chill Lo-Fi", desc: "Warm hip-hop groove" },
                { id: "upbeat_tech", label: "⚡ Upbeat Tech", desc: "High energy & punchy" },
                { id: "epic_cinematic", label: "🎬 Cinematic Tension", desc: "Dramatic build" },
              ].map((m) => (
                <button
                  key={m.id}
                  onClick={() => setMusicTrack(m.id)}
                  className={`p-2.5 rounded-lg border text-left transition-all ${
                    musicTrack === m.id
                      ? "bg-primary/15 border-primary text-primary shadow-sm"
                      : "bg-background border-border text-foreground hover:border-white/20"
                  }`}
                >
                  <p className="text-xs font-semibold">{m.label}</p>
                  <p className="text-[10px] text-cf-muted mt-0.5">{m.desc}</p>
                </button>
              ))}
            </div>
          </section>

          {/* Section 6: Motion & Visual Effects */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-primary uppercase tracking-wider">6. Motion & Visual Effects</h3>
              <span className="text-[10px] text-muted-foreground">All 6 Effects Verified</span>
            </div>

            {selectedEffects.length > 2 && (
              <div className="p-2 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[11px] leading-tight">
                ⚠️ Stacking more than 2 effects may reduce clarity.
              </div>
            )}

            <div className="grid grid-cols-2 gap-2">
              {[
                { id: "film_grain", label: "🎞️ Film Grain", status: "active" },
                { id: "vignette", label: "🎬 Vignette", status: "active" },
                { id: "zoom", label: "🔍 Push-In Zoom", status: "active" },
                { id: "camera_shake", label: "📳 Handheld Shake", status: "active" },
                { id: "rgb_split", label: "🌈 RGB Glitch", status: "active" },
                { id: "vhs_noise", label: "📼 VHS Retro", status: "active" },
              ].map((eff) => {
                const isAvailable = eff.status === "active";
                const isSelected = selectedEffects.includes(eff.id);

                return (
                  <button
                    key={eff.id}
                    disabled={!isAvailable}
                    onClick={() => isAvailable && toggleEffect(eff.id)}
                    className={`p-2.5 rounded-lg border text-xs font-medium text-left transition-all relative flex flex-col justify-between ${
                      !isAvailable
                        ? "opacity-40 bg-muted/20 border-border text-muted-foreground cursor-not-allowed"
                        : isSelected
                        ? "bg-primary/15 border-primary text-primary shadow-sm"
                        : "bg-background border-border text-foreground hover:border-white/20"
                    }`}
                  >
                    <span>{eff.label}</span>
                    {!isAvailable && (
                      <span className="text-[9px] text-muted-foreground font-mono mt-1">
                        [{eff.status}]
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
