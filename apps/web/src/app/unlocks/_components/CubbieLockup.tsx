import { CrewbieLogo } from "./CrewbieLogo";
import styles from "../unlocks.module.css";

// A text wordmark for Cubbie. Swap in the official logo here if the Cubbie team supplies one.
export function CubbieLockup() {
  return <span className={styles.lockup}>
    <span className={styles.cubbieWord}>Cubbie</span>
    <span className={styles.times} aria-hidden="true">×</span>
    <CrewbieLogo />
  </span>;
}
