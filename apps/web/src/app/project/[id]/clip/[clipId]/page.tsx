"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";

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
  review_status: string;
}

export default function ClipEditorPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const clipId = params.clipId as string;

  const [clip, setClip] = useState<ClipDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [rerendering, setRerendering] = useState(false);

  // Editor form state
  const [startSec, setStartSec] = useState<number>(0);
  const [endSec, setEndSec] = useState<number>(30);
  const [captionStyle, setCaptionStyle] = useState<string>("bold_karaoke");
  const [cropMode, setCropMode] = useState<string>("face_track");
  const [voiceId, setVoiceId] = useState<string>("en-US-JennyNeural");
  const [voiceoverText, setVoiceoverText] = useState<string>("");
  const [musicTrack, setMusicTrack] = useState<string>("none");
  const [selectedEffects, setSelectedEffects] = useState<string[]>([]);
  const [viewMode, setViewMode] = useState<"preview" | "split">("preview");

  const fetchClip = useCallback(async () => {
    try {
      const res = await fetch(`http://localhost:8000/api/projects/${projectId}/clips`);
      if (!res.ok) throw new Error("Failed to load clips");
      const clips: ClipDetail[] = await res.json();
      const found = clips.find((c) => c.id === clipId);
      if (found) {
        setClip(found);
        setStartSec(found.start_sec);
        setEndSec(found.end_sec);
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
        music_track: musicTrack,
        effects: selectedEffects.map((e) => ({ id: e, intensity: 0.5 })),
      };

      const res = await fetch(`http://localhost:8000/api/clips/${clipId}/rerender`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error("Re-render failed");
      const data = await res.json();
      toast.success("Clip re-rendered successfully!");
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
    ? clip.file_url.startsWith("media")
      ? `http://localhost:8000/${clip.file_url}`
      : clip.file_url
    : "";

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-foreground">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-background text-foreground overflow-hidden">
      {/* Header */}
      <header className="h-14 border-b border-border px-6 flex items-center justify-between flex-shrink-0 bg-card">
        <div className="flex items-center gap-3">
          <Link
            href={`/project/${projectId}`}
            className="text-xs text-cf-muted hover:text-white flex items-center gap-1"
          >
            ← Back to Project
          </Link>
          <span className="text-cf-muted">/</span>
          <h1 className="text-sm font-semibold">Clip Editor &amp; Brand Studio</h1>
          {clip?.transformation_score !== undefined && (
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                (clip.transformation_score || 0) >= 70
                  ? "bg-cf-success/15 text-cf-success border-cf-success/30"
                  : "bg-primary/15 text-primary border-primary/30"
              }`}
            >
              ✨ {clip.transformation_score}/100 Transformation
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <div className="flex bg-background rounded-lg border border-border p-0.5">
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

          <button
            onClick={handleRerender}
            disabled={rerendering}
            className="bg-primary text-primary-foreground px-4 py-1.5 rounded-lg text-xs font-semibold hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1.5"
          >
            {rerendering ? (
              <>
                <div className="animate-spin h-3.5 w-3.5 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full" />
                Rendering...
              </>
            ) : (
              "⚡ Re-render Clip"
            )}
          </button>
        </div>
      </header>

      {/* Main Studio Grid */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
        {/* Left / Center: Video Player */}
        <div className="lg:col-span-7 bg-zinc-950 flex items-center justify-center p-6 relative overflow-hidden border-r border-border">
          {viewMode === "preview" ? (
            <div className="h-full max-h-[750px] aspect-[9/16] bg-black rounded-2xl overflow-hidden shadow-2xl border border-white/10 relative">
              {videoUrl ? (
                <video src={videoUrl} controls className="w-full h-full object-cover" />
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
                  {videoUrl && <video src={videoUrl} controls className="w-full h-full object-cover" />}
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
            <h3 className="text-xs font-bold text-primary uppercase tracking-wider">4. Voiceover &amp; TTS Narration</h3>
            <div>
              <label className="text-xs text-cf-muted block mb-1">Studio Voice Persona</label>
              <select
                value={voiceId}
                onChange={(e) => setVoiceId(e.target.value)}
                className="w-full rounded-lg bg-background border border-border px-3 py-2 text-xs"
              >
                <option value="en-US-JennyNeural">Bella — Warm Explainer (US Female)</option>
                <option value="en-US-GuyNeural">Adam — Dynamic Host (US Male)</option>
                <option value="en-GB-SoniaNeural">Emma — British Commentary (UK Female)</option>
                <option value="en-GB-RyanNeural">George — British Documentary (UK Male)</option>
                <option value="en-US-AriaNeural">Sarah — Authoritative News (US Female)</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-cf-muted block mb-1">Original Commentary Script</label>
              <textarea
                value={voiceoverText}
                onChange={(e) => setVoiceoverText(e.target.value)}
                rows={3}
                placeholder="Enter original commentary to be voiced over and duck source audio by -12dB..."
                className="w-full rounded-lg bg-background border border-border p-3 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </section>

          {/* Section 5: Background Music */}
          <section className="space-y-3">
            <h3 className="text-xs font-bold text-primary uppercase tracking-wider">5. Background Music Bed</h3>
            <select
              value={musicTrack}
              onChange={(e) => setMusicTrack(e.target.value)}
              className="w-full rounded-lg bg-background border border-border px-3 py-2 text-xs"
            >
              <option value="none">No Background Music</option>
              <option value="ambient_focus">Ambient Focus (Lo-Volume Pad)</option>
              <option value="lofi_beats">Chill Lo-Fi Beats</option>
              <option value="upbeat_tech">Upbeat Modern Tech</option>
              <option value="epic_cinematic">Cinematic Tension</option>
            </select>
          </section>

          {/* Section 6: Motion & Visual Effects */}
          <section className="space-y-3">
            <h3 className="text-xs font-bold text-primary uppercase tracking-wider">6. Motion Effects</h3>
            <div className="grid grid-cols-2 gap-2">
              {[
                { id: "film_grain", label: "🎞️ Film Grain" },
                { id: "vignette", label: "🎬 Vignette" },
                { id: "camera_shake", label: "📳 Handheld Shake" },
                { id: "zoom", label: "🔍 Push-In Zoom" },
                { id: "rgb_split", label: "🌈 RGB Glitch" },
                { id: "vhs_noise", label: "📼 VHS Retro" },
              ].map((eff) => (
                <button
                  key={eff.id}
                  onClick={() => toggleEffect(eff.id)}
                  className={`p-2.5 rounded-lg border text-xs font-medium text-left transition-all ${
                    selectedEffects.includes(eff.id)
                      ? "bg-primary/15 border-primary text-primary"
                      : "bg-background border-border text-cf-muted hover:border-white/20"
                  }`}
                >
                  {eff.label}
                </button>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
