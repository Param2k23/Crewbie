import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { motion } from "./motion.config";
import { planningExamples } from "./planningExamples";

export function animatePlan(element: HTMLElement, repeat = true) {
  const panel = element.querySelector<HTMLElement>("[data-planning-panel]")!;
  const lines = Array.from(panel.querySelectorAll<HTMLElement>("[data-plan-line]"));
  const lights = panel.querySelectorAll("[data-step-light]");
  const checks = panel.querySelectorAll("[data-step-check]");
  const connectors = panel.querySelectorAll("[data-step-connector]");
  let example = 0;
  const timeline = gsap.timeline({
    paused: true, repeat: repeat ? -1 : 0, repeatDelay: motion.planning.hold,
    onRepeat: () => {
      example = (example + 1) % planningExamples.length;
      lines.forEach((line, index) => { line.textContent = planningExamples[example]![index]!; });
      panel.querySelector("[data-example-index]")!.textContent = String(example + 1);
    },
  });
  timeline.set(lines, { opacity: 0, y: 8 }).set(lights, { opacity: 0.15 })
    .set(checks, { strokeDasharray: 1, strokeDashoffset: 1 }).set(connectors, { scaleY: 0 });
  lines.forEach((line, index) => {
    timeline.to(lights[index]!, { opacity: 1, duration: motion.duration.settle, ease: motion.ease.reveal })
      .to(line, { opacity: 1, y: 0, duration: motion.duration.reveal, ease: motion.ease.reveal }, "<")
      .to(checks[index]!, { strokeDashoffset: 0, duration: motion.duration.settle, ease: motion.ease.scroll });
    if (index < 2) timeline.to(connectors[index]!, { scaleY: 1, duration: motion.duration.settle, ease: motion.ease.scroll });
  });
  let trigger: ScrollTrigger | undefined;
  function sync() { timeline.paused(!trigger?.isActive || document.hidden); }
  trigger = ScrollTrigger.create({ trigger: panel, start: "top 88%", end: "bottom top", onToggle: sync });
  document.addEventListener("visibilitychange", sync);
  sync();
  return () => {
    document.removeEventListener("visibilitychange", sync);
    timeline.kill();
    trigger?.kill();
    lines.forEach((line, index) => { line.textContent = planningExamples[0][index]!; });
    panel.querySelector("[data-example-index]")!.textContent = "1";
  };
}
