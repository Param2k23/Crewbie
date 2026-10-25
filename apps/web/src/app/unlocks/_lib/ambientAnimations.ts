import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { motion } from "./motion.config";

export function animateAmbient(element: HTMLElement, enabled: boolean) {
  if (!enabled) return () => {};
  const disposers: Array<() => void> = [];
  function own(animation: gsap.core.Animation, target: Element) {
    animation.pause();
    let trigger: ScrollTrigger | undefined;
    const sync = () => animation.paused(!trigger?.isActive || document.hidden);
    trigger = ScrollTrigger.create({ trigger: target, start: "top bottom", end: "bottom top", onToggle: sync });
    document.addEventListener("visibilitychange", sync);
    sync();
    disposers.push(() => { document.removeEventListener("visibilitychange", sync); trigger?.kill(); animation.kill(); });
  }

  element.querySelectorAll<HTMLElement>("[data-blob]").forEach((blob, index) => {
    own(gsap.to(blob, {
      xPercent: index ? -18 : 18, yPercent: index ? 16 : -12, rotation: index ? -12 : 12,
      duration: motion.ambient.blobs[index]!, repeat: -1, yoyo: true, ease: motion.ambient.ease,
    }), element.querySelector("[data-hero]")!);
  });
  element.querySelectorAll<HTMLElement>("[data-float]").forEach((card, index) => {
    own(gsap.to(card, {
      y: index % 2 ? 9 : -9, rotation: "+=2", delay: index * .7,
      duration: motion.ambient.floats[index % motion.ambient.floats.length]!,
      repeat: -1, yoyo: true, ease: motion.ambient.ease,
    }), element.querySelector("[data-hero]")!);
  });
  const track = element.querySelector<HTMLElement>("[data-marquee-track]")!;
  own(gsap.to(track, { xPercent: -50, duration: motion.ambient.marquee, repeat: -1, ease: motion.ease.scroll }), track.parentElement!);
  element.querySelectorAll<HTMLElement>("[data-cta]").forEach((button) => {
    own(gsap.fromTo(button.querySelector("[data-cta-ring]"), { scale: 1, opacity: .2 }, {
      scale: 1.065, opacity: .6, duration: motion.ambient.glow, repeat: -1, yoyo: true, ease: motion.ambient.ease,
    }), button);
    const stripe = button.querySelector("[data-cta-shine]");
    const shine = gsap.timeline({ repeat: -1, repeatDelay: motion.ambient.shineDelay });
    shine.set(stripe, { x: 0, xPercent: -120, opacity: .7 })
      .to(stripe, { x: 0, xPercent: 420, duration: motion.ambient.shine, ease: motion.ease.scroll })
      // Clear the reflection before the repeat delay; it never parks on an edge.
      .set(stripe, { opacity: 0, xPercent: -120 });
    own(shine, button);
  });
  return () => disposers.forEach((dispose) => dispose());
}
