import gsap from "gsap";
import { SplitText } from "gsap/SplitText";
import { motion } from "./motion.config";
import { animatePlan } from "./planningAnimation";

export function revealHeadlines(element: HTMLElement, desktop: boolean) {
  return Array.from(element.querySelectorAll<HTMLElement>("[data-headline]")).map((headline) =>
    SplitText.create(headline, {
      type: "lines,words", mask: "lines", autoSplit: true,
      onSplit(self) {
        return gsap.from(self.lines, {
          yPercent: desktop ? 105 : 0,
          opacity: 0,
          duration: motion.duration.reveal,
          stagger: motion.stagger,
          ease: motion.ease.reveal,
          scrollTrigger: { trigger: headline, start: "top 92%", once: true },
        });
      },
    }),
  );
}

export function animateSections(element: HTMLElement, desktop: boolean, continuous = true) {
  const disposePlan = animatePlan(element, continuous);
  const counters = Array.from(element.querySelectorAll<HTMLElement>("[data-counter]"));
  counters.forEach((counter) => {
    const value = { number: 0 };
    gsap.to(value, { number: Number(counter.dataset.counter), duration: motion.duration.reveal, ease: motion.ease.reveal,
      onUpdate: () => { counter.textContent = String(Math.round(value.number)); },
      scrollTrigger: { trigger: counter, start: "top 88%", once: true },
    });
  });
  const dispose = () => { disposePlan(); counters.forEach((counter) => { counter.textContent = counter.dataset.counter!; }); };
  element.querySelectorAll<HTMLElement>("[data-reveal-group]").forEach((group) => {
    gsap.from(group.querySelectorAll("[data-reveal-card]"), {
      y: desktop ? 32 : 0,
      opacity: 0,
      duration: motion.duration.reveal,
      stagger: motion.stagger,
      ease: motion.ease.reveal,
      scrollTrigger: { trigger: group, start: "top 88%", once: true },
    });
  });

  gsap.from(element.querySelectorAll("[data-crew-card]"), {
    x: desktop ? 48 : 0,
    opacity: 0,
    duration: motion.duration.reveal,
    stagger: motion.stagger,
    ease: motion.ease.reveal,
    scrollTrigger: { trigger: element.querySelector("[data-crew-composition]"), start: "top 80%", once: true },
  });

  gsap.from(element.querySelectorAll("[data-final-reveal]"), {
    y: desktop ? 12 : 0,
    opacity: 0,
    duration: motion.duration.settle,
    stagger: motion.stagger,
    ease: motion.ease.reveal,
    scrollTrigger: { trigger: element.querySelector("[data-finale]"), start: "top 80%", once: true },
  });

  if (!desktop) return dispose;
  gsap.to(element.querySelector("[data-hero-composition]"), {
    y: 40,
    duration: motion.duration.settle,
    ease: motion.ease.scroll,
    scrollTrigger: {
      trigger: element.querySelector("[data-hero]"), start: "top top", end: "bottom top",
      scrub: motion.duration.settle,
    },
  });
  gsap.to(element.querySelectorAll("[data-parallax-background]"), {
    y: -50, duration: motion.duration.settle, ease: motion.ease.scroll,
    scrollTrigger: { trigger: element.querySelector("[data-hero]"), start: "top top", end: "bottom top", scrub: motion.duration.settle },
  });
  return dispose;
}
