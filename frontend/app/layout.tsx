import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Real Estate AI SaaS",
  description: "AI-powered lead management for real estate agencies"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
