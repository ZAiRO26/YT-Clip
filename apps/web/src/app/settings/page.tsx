"use client";

import { useEffect, useState } from "react";
import { LLMSettings, api } from "@/lib/api";
import { Save, Server, Loader2, CheckCircle2, XCircle, ArrowLeft } from "lucide-react";
import toast from "react-hot-toast";
import Link from "next/link";

export default function SettingsPage() {
  const [settings, setSettings] = useState<LLMSettings>({
    llm_base_url: "",
    llm_api_key: "",
    llm_model: "",
  });
  
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: string; message: string; models?: string[] } | null>(null);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await api.getSettings();
        setSettings(data);
      } catch (error) {
        console.error("Failed to load settings:", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setSettings({ ...settings, [e.target.name]: e.target.value });
    // Clear test result on change
    setTestResult(null);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await api.updateSettings(settings);
      toast.success("Settings saved successfully!");
    } catch (error) {
      console.error("Failed to save settings:", error);
      toast.error("Failed to save settings");
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const result = await api.testConnection(settings);
      setTestResult(result);
    } catch (error) {
      setTestResult({ status: "error", message: String(error) });
    } finally {
      setIsTesting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-cf-primary" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8 p-6">
      <div>
        <Link href="/dashboard" className="inline-flex items-center text-sm font-medium text-cf-muted-fg hover:text-white transition-colors mb-4">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Dashboard
        </Link>
        <h1 className="text-3xl font-bold tracking-tight text-white">Settings</h1>
        <p className="mt-2 text-cf-muted-fg">
          Configure the LLM gateway for clip selection. ClipForge supports any OpenAI-compatible API (OmniRoute, FreeLLMAPI, vLLM, etc).
        </p>
      </div>

      <div className="rounded-xl border border-cf-border bg-cf-card shadow-sm">
        <form onSubmit={handleSave} className="space-y-6 p-6">
          
          {/* Base URL */}
          <div className="space-y-2">
            <label htmlFor="llm_base_url" className="block text-sm font-medium text-white">
              LLM API Base URL
            </label>
            <div className="relative flex items-center">
              <Server className="absolute left-3 h-5 w-5 text-cf-muted-fg" />
              <input
                id="llm_base_url"
                name="llm_base_url"
                type="url"
                required
                value={settings.llm_base_url}
                onChange={handleChange}
                placeholder="http://localhost:8080/v1"
                className="block w-full rounded-md border-cf-border bg-cf-bg py-2 pl-10 pr-3 text-white placeholder-cf-muted-fg focus:border-cf-primary focus:ring-1 focus:ring-cf-primary sm:text-sm"
              />
            </div>
            <p className="text-xs text-cf-muted-fg">Must end in /v1 for OpenAI compatibility</p>
          </div>

          {/* API Key */}
          <div className="space-y-2">
            <label htmlFor="llm_api_key" className="block text-sm font-medium text-white">
              API Key
            </label>
            <input
              id="llm_api_key"
              name="llm_api_key"
              type="password"
              value={settings.llm_api_key}
              onChange={handleChange}
              placeholder="not-needed"
              className="block w-full rounded-md border-cf-border bg-cf-bg py-2 px-3 text-white placeholder-cf-muted-fg focus:border-cf-primary focus:ring-1 focus:ring-cf-primary sm:text-sm"
            />
          </div>

          {/* Model */}
          <div className="space-y-2">
            <label htmlFor="llm_model" className="block text-sm font-medium text-white">
              Model Name <span className="text-cf-muted-fg text-xs font-normal ml-2">(Test connection to load available models)</span>
            </label>
            {testResult?.models && testResult.models.length > 0 ? (
              <select
                id="llm_model"
                name="llm_model"
                required
                value={settings.llm_model}
                onChange={handleChange}
                className="block w-full rounded-md border-cf-border bg-cf-bg py-2 px-3 text-white focus:border-cf-primary focus:ring-1 focus:ring-cf-primary sm:text-sm appearance-none"
              >
                <option value="auto">auto (Default)</option>
                {Array.from(new Set(testResult.models)).map((m, idx) => (
                  <option key={`${m}-${idx}`} value={m}>{m}</option>
                ))}
              </select>
            ) : (
              <input
                id="llm_model"
                name="llm_model"
                type="text"
                required
                value={settings.llm_model}
                onChange={handleChange}
                placeholder="auto"
                className="block w-full rounded-md border-cf-border bg-cf-bg py-2 px-3 text-white placeholder-cf-muted-fg focus:border-cf-primary focus:ring-1 focus:ring-cf-primary sm:text-sm"
              />
            )}
          </div>

          <div className="pt-4 pb-2">
            <h2 className="text-lg font-semibold text-white">Local Export Destination</h2>
            <p className="text-sm text-cf-muted-fg mb-4">
              When a clip is marked as "Approved", it will automatically be copied to this folder.
            </p>
            <div className="space-y-2">
              <label htmlFor="export_path" className="block text-sm font-medium text-white">
                Export Folder Path
              </label>
              <input
                id="export_path"
                name="export_path"
                type="text"
                value={settings.export_path || ""}
                onChange={handleChange}
                placeholder="e.g. D:\MyVideos\Exports"
                className="block w-full rounded-md border-cf-border bg-cf-bg py-2 px-3 text-white placeholder-cf-muted-fg focus:border-cf-primary focus:ring-1 focus:ring-cf-primary sm:text-sm"
              />
            </div>
          </div>

          {/* Actions & Test Result */}
          <div className="pt-4 border-t border-cf-border space-y-4">
            <div className="flex items-center space-x-4">
              <button
                type="submit"
                disabled={isSaving}
                className="flex items-center justify-center rounded-md bg-cf-primary px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-cf-primary/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cf-primary disabled:opacity-50"
              >
                {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                Save Settings
              </button>
              
              <button
                type="button"
                onClick={handleTest}
                disabled={isTesting}
                className="flex items-center justify-center rounded-md bg-cf-bg border border-cf-border px-4 py-2 text-sm font-semibold text-white hover:bg-cf-bg/80 disabled:opacity-50"
              >
                {isTesting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : "Test Connection"}
              </button>
            </div>

            {/* Test Results */}
            {testResult && (
              <div className={`p-4 rounded-md flex items-start ${testResult.status === 'success' ? 'bg-green-500/10 border border-green-500/20' : 'bg-red-500/10 border border-red-500/20'}`}>
                {testResult.status === 'success' ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500 mt-0.5 mr-3 shrink-0" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-500 mt-0.5 mr-3 shrink-0" />
                )}
                <div>
                  <h4 className={`text-sm font-medium ${testResult.status === 'success' ? 'text-green-400' : 'text-red-400'}`}>
                    {testResult.status === 'success' ? 'Connection Successful' : 'Connection Failed'}
                  </h4>
                  <p className="mt-1 text-sm text-cf-muted-fg">{testResult.message}</p>
                  
                  {testResult.models && testResult.models.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-cf-muted-fg mb-1">Available Models:</p>
                      <div className="flex flex-wrap gap-2">
                        {Array.from(new Set(testResult.models)).slice(0, 5).map((m, idx) => (
                          <span key={`${m}-${idx}`} className="px-2 py-1 text-xs rounded bg-cf-bg border border-cf-border text-white">
                            {m}
                          </span>
                        ))}
                        {Array.from(new Set(testResult.models)).length > 5 && (
                          <span className="px-2 py-1 text-xs rounded bg-cf-bg text-cf-muted-fg">
                            +{Array.from(new Set(testResult.models)).length - 5} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </form>
      </div>

      {/* Rights & Originality Checklist (context2-upgrade.md Section 2.2 & 6.2) */}
      <div className="rounded-lg border border-border bg-card p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-2">
          <span className="text-base">🛡️</span>
          <h3 className="text-sm font-bold text-foreground">Rights &amp; Originality Editorial Checklist</h3>
        </div>
        <p className="text-xs text-cf-muted leading-relaxed">
          ClipForge AI is an editorial studio designed to assist transformative clipping. Ensure your project meets monetization standards:
        </p>

        <div className="space-y-2.5 pt-2">
          {[
            {
              title: "1. Verified Source Rights Foundation",
              desc: "Ensure you own the footage, hold explicit commercial licensing, or have explicit written permission from the rights holder.",
            },
            {
              title: "2. Significant Transformative Commentary",
              desc: "Add original analytical voiceover, reaction framing, or educational callout overlays rather than raw re-uploading.",
            },
            {
              title: "3. Editorial Speech Boundary Integrity",
              desc: "Cut at natural breath and speech boundaries (no clipped words or mid-sentence breaks).",
            },
            {
              title: "4. Explicit Rights Acknowledgment",
              desc: "Review and accept the pre-export rights acknowledgment dialog before publishing to social platforms.",
            },
          ].map((item, idx) => (
            <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-background border border-border">
              <span className="text-primary font-bold text-xs mt-0.5">✓</span>
              <div>
                <h4 className="text-xs font-semibold text-foreground">{item.title}</h4>
                <p className="text-[11px] text-cf-muted mt-0.5">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
