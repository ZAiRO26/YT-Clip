import type { Metadata } from "next";
import { Inter, Geist_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ClipForge AI",
  description:
    "AI-powered tool that turns YouTube videos into ready-to-post vertical clips, scored against your campaign brief.",
};

import { Toaster } from "react-hot-toast";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {children}
        <Toaster position="bottom-right" toastOptions={{ className: 'dark-toast', style: { background: '#1E1E24', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' } }} />
      </body>
    </html>
  );
}
