import { planningExamples } from "../_lib/planningExamples";
import styles from "../unlocks.module.css";

export function PlanningPanel() {
  return <div className={styles.planningPanel} data-planning-panel aria-live="off">
    <div className={styles.panelCaption}><span data-counter="3">3</span> steps · Illustrative example <span data-example-index>1</span> / 3</div>
    <ol className={styles.planSteps}>
      {["Request", "Practical checks", "Personal plan"].map((label, index) =>
        <li key={label} data-plan-step>
          <span className={styles.stepNumber}><span data-step-light aria-hidden="true" /><b>{index + 1}</b></span>
          {index < 2 && <span className={styles.stepConnector} aria-hidden="true"><i data-step-connector /></span>}
          <div className={styles.stepBody}><h3>{label}</h3><p data-plan-line>{planningExamples[0][index]}</p></div>
          <svg className={styles.stepCheck} viewBox="0 0 24 24" aria-hidden="true"><path data-step-check pathLength="1" d="m5 12 4 4L19 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </li>)}
    </ol>
    <p className={styles.caption}>A preview, not a live request. Details still need verification.</p>
  </div>;
}
