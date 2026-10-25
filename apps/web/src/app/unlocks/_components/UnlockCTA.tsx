import Link from "next/link";
import styles from "../unlocks.module.css";

export function UnlockCTA({ quiet = false, label = "See how Cubbie does it", href = "#how-it-works" }: { quiet?: boolean; label?: string; href?: string }) {
  return <Link className={styles.cta} href={href} data-cta data-final-reveal={quiet || undefined}>
    <span className={styles.ctaRing} data-cta-ring aria-hidden="true" />
    <span className={styles.ctaShine} aria-hidden="true"><i data-cta-shine /></span>
    <span>{label}</span><span aria-hidden="true">↗</span>
  </Link>;
}
