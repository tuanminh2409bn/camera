import type { Metadata } from "next";
import "./globals.css";
export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Camera — Giám sát riêng tư",
  description: "Không gian giám sát camera riêng tư",
  robots: { index: false, follow: false },
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
