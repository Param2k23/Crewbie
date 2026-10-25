"use client";

import { useEffect, useState } from "react";
import { HERO_ROTATE_MS, heroLanguages } from "../_lib/languages";
import styles from "../unlocks.module.css";

/**
 * Last line of the hero headline, cycling through languages. Every phrase sits in the same grid cell, so the
 * line keeps the width of the longest one and nothing shifts. Reduced-motion visitors keep the English line.
 */
export function LanguageRotator() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const quiet = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (quiet.matches) return;
    const timer = window.setInterval(() => setActive((i) => (i + 1) % heroLanguages.length), HERO_ROTATE_MS);
    return () => window.clearInterval(timer);
  }, []);

  return <span className={styles.rotator} aria-hidden="true" data-language-rotator>
    {heroLanguages.map((language, i) => (
      <span key={language.code} lang={language.code} className={styles.rotatorItem} data-active={i === active || undefined}>
        {language.text}
      </span>
    ))}
    <span className={styles.rotatorName}>{heroLanguages[active]?.name}</span>
  </span>;
}
