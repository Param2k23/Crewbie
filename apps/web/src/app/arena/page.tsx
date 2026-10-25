import { MissionControlApp } from "@/components/MissionControlApp";

export const metadata = { title: "Mission Control · Crewbie" };

export default async function ArenaPage({ searchParams }: { searchParams: Promise<{ mode?: string; view?: string }> }) {
  const sp = await searchParams;
  const mode = sp.mode === "fixture" || sp.mode === "live" || sp.mode === "weekend" ? sp.mode : "quick"; // "demo" is an alias for quick
  const view = sp.view === "2d" ? "2d" : sp.view === "3d" ? "3d" : undefined;
  return <MissionControlApp initialMode={mode} initialView={view} />;
}
