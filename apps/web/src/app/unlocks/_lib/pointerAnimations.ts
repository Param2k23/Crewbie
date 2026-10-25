import gsap from "gsap";
import { motion } from "./motion.config";

export function animatePointers(element: HTMLElement) {
  const disposers: Array<() => void> = [];
  element.querySelectorAll<HTMLElement>("[data-tilt]").forEach((card) => {
    gsap.set(card, { transformPerspective: 900 });
    const config = { duration: motion.duration.settle, ease: motion.ease.reveal };
    const x = gsap.quickTo(card, "rotationX", config);
    const y = gsap.quickTo(card, "rotationY", config);
    const sheen = card.querySelector("[data-card-sheen]")!;
    const sx = gsap.quickTo(sheen, "xPercent", config);
    const sy = gsap.quickTo(sheen, "yPercent", config);
    const alpha = gsap.quickTo(sheen, "opacity", config);
    const move = (event: PointerEvent) => {
      if (event.pointerType === "touch") return;
      const box = card.getBoundingClientRect();
      const px = (event.clientX - box.left) / box.width - .5;
      const py = (event.clientY - box.top) / box.height - .5;
      x(-py * 8); y(px * 10); sx(px * 35); sy(py * 35); alpha(1);
    };
    const leave = () => { x(0); y(0); sx(0); sy(0); alpha(0); };
    card.addEventListener("pointermove", move);
    card.addEventListener("pointerleave", leave);
    disposers.push(() => { card.removeEventListener("pointermove", move); card.removeEventListener("pointerleave", leave); });
  });
  element.querySelectorAll<HTMLElement>("[data-cta]").forEach((button) => {
    const config = { duration: motion.duration.settle, ease: motion.ease.reveal };
    const x = gsap.quickTo(button, "x", config);
    const y = gsap.quickTo(button, "y", config);
    const move = (event: PointerEvent) => {
      const box = button.getBoundingClientRect();
      x((event.clientX - box.left - box.width / 2) * .12);
      y((event.clientY - box.top - box.height / 2) * .16);
    };
    const leave = () => { x(0); y(0); };
    button.addEventListener("pointermove", move);
    button.addEventListener("pointerleave", leave);
    disposers.push(() => { button.removeEventListener("pointermove", move); button.removeEventListener("pointerleave", leave); });
  });
  return () => disposers.forEach((dispose) => dispose());
}
