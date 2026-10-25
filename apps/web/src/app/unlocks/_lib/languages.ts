/** "Make plans happen." in the languages Cubbie can reply in. English first: it is the server-rendered default. */
export const heroLanguages = [
  { code: "en", name: "English", text: "Make plans happen." },
  { code: "es", name: "Español", text: "Haz que los planes pasen." },
  { code: "hi", name: "हिन्दी", text: "योजनाओं को हकीकत बनाओ।" },
  { code: "zh", name: "中文", text: "让计划成真。" },
  { code: "fr", name: "Français", text: "Fais vivre tes plans." },
  { code: "ko", name: "한국어", text: "계획을 현실로." },
  { code: "pt", name: "Português", text: "Tire os planos do papel." },
  { code: "ja", name: "日本語", text: "計画を実現しよう。" },
] as const;

export const HERO_ROTATE_MS = 2800;
