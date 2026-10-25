import styles from "../unlocks.module.css";

type LogoVariant = "unlock" | "cards";

// Change to "cards" to use placeholder option (b) in both the header and footer.
const defaultVariant: LogoVariant = "unlock";

export function CrewbieLogo({ variant = defaultVariant }: { variant?: LogoVariant }) {
  return (
    <svg className={styles.logo} viewBox="0 0 215 44" role="img" aria-label="Crewbie">
      {variant === "unlock" ? (
        // Placeholder option (a): original rounded unlock card with a keyhole cutout.
        <path className={styles.logoSymbol} fill="currentColor" fillRule="evenodd"
          d="M9 7h22a5 5 0 0 1 5 5v21a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V12a5 5 0 0 1 5-5Zm11 8a4 4 0 0 1 2 7.464V28h-4v-5.536A4 4 0 0 1 20 15Z" />
      ) : (
        // Placeholder option (b): original three overlapping rounded squares.
        <g className={styles.logoSymbol} fill="none" stroke="currentColor" strokeWidth="2.5">
          <rect x="2" y="5" width="23" height="23" rx="5" />
          <rect x="8" y="11" width="23" height="23" rx="5" />
          <rect x="14" y="17" width="23" height="23" rx="5" />
        </g>
      )}
      <text className={styles.logoWordmark} x="47" y="32" fill="currentColor">Crewbie</text>
    </svg>
  );
}
