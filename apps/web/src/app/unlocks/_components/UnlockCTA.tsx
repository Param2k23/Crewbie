import Link from "next/link";
import styles from "../unlocks.module.css";

export function UnlockCTA({ quiet = false }: { quiet?: boolean }) {
  return <Link className={styles.cta} href="#how-it-works" data-cta data-final-reveal={quiet || undefined}>
    <span className={styles.ctaRing} data-cta-ring aria-hidden="true" />
    <span className={styles.ctaShine} aria-hidden="true"><i data-cta-shine /></span>
    <span>Find my next unlock</span><span aria-hidden="true">↗</span>
  </Link>;
}
