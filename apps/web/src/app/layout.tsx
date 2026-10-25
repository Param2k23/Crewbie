import type { Metadata, Viewport } from "next";
import "./globals.css";
import { SiteNav } from "@/components/SiteNav";

export const metadata: Metadata = {
  title: "Crewbie Mission Control",
  description: "Campus Pulse and a 3D Negotiation Arena driven by real agent events. Synthetic demo data is labeled.",
};
export const viewport: Viewport = { colorScheme: "light dark", themeColor: "#0b1020" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip" href="#main">Skip to content</a>
        <SiteNav />
        <main id="main">{children}</main>
      </body>
    </html>
  );
}
