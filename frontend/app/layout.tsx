import type { Metadata } from "next";
import "./globals.css";
import { SessionProvider } from "../contexts/SessionContext";
import { ToastProvider } from "../contexts/ToastContext";

export const metadata: Metadata = {
  title: "Docker MCP Gateway Console",
  description: "Web console for managing Docker-based MCP servers",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body>
        <SessionProvider>
          <ToastProvider>
            {children}
          </ToastProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
