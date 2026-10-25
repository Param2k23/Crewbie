"use client";

import { useRef, type ReactNode } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import Lenis from "lenis";
import { motion } from "../_lib/motion.config";
import { animateSections, revealHeadlines } from "../_lib/sectionAnimations";
import { animateAmbient } from "../_lib/ambientAnimations";
import { animatePointers } from "../_lib/pointerAnimations";
import { SceneMotionContext, type SceneMotion } from "./SceneMotion";
import styles from "../unlocks.module.css";

gsap.registerPlugin(useGSAP, ScrollTrigger, SplitText);

export function ScrollStory({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  // The scene reads this instance-local state without React renders per scroll tick.
  const scroll = useRef<SceneMotion>({ progress: 0, hero: 0, pointer: { x: 0, y: 0 }, anchor: { x: .75, y: .5 } });

  useGSAP(() => {
    const element = root.current;
    if (!element) return;
    let disposed = false;
    const lowPower = (navigator.hardwareConcurrency || 8) <= 4;
    element.toggleAttribute("data-ambient-off", lowPower);
    const media = gsap.matchMedia();

    // Waiting here avoids splitting against fallback font metrics. The cancellation
    // guard also prevents setup after a route change or Strict Mode teardown.
    void document.fonts.ready.then(() => {
      if (disposed) return;
      media.add({ desktop: motion.desktop, reduced: motion.reduced, all: "all" }, (context) => {
        const { desktop, reduced } = context.conditions!;
        if (reduced) return;
        let lenis: Lenis | undefined;
        const tick = (seconds: number) => lenis?.raf(seconds * 1000);
        if (desktop) {
          lenis = new Lenis({ autoRaf: false, smoothWheel: true, syncTouch: false, lerp: 0.1, anchors: false });
          lenis.on("scroll", ScrollTrigger.update);
          gsap.ticker.lagSmoothing(0);
          gsap.ticker.add(tick);
        }

        const setPageProgress = gsap.quickSetter(element.querySelector("[data-page-progress]"), "scaleX");
        const measureAnchor = () => {
          const rect = element.querySelector("[data-hero-composition]")!.getBoundingClientRect();
          scroll.current.anchor.x = (rect.left + rect.width / 2) / innerWidth;
          scroll.current.anchor.y = (rect.top + rect.height / 2) / innerHeight;
        };
        const heroProgress = ScrollTrigger.create({
          trigger: element.querySelector("[data-hero]"), start: "top top", end: "bottom top",
          onUpdate: (self) => { scroll.current.hero = self.progress; measureAnchor(); }, onRefresh: measureAnchor,
        });
        measureAnchor();
        const pointer = (event: PointerEvent) => {
          scroll.current.pointer.x = event.clientX / innerWidth * 2 - 1;
          scroll.current.pointer.y = event.clientY / innerHeight * 2 - 1;
        };
        element.addEventListener("pointermove", pointer);
        const anchorClick = (event: MouseEvent) => {
          if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
          const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>('a[href^="#"]') : null;
          const target = link?.hash ? document.getElementById(decodeURIComponent(link.hash.slice(1))) : null;
          if (!link || !target) return;
          // Let Next's patched History API preserve route state, while one scroll
          // owner handles movement instead of Next and Lenis both scrolling.
          event.preventDefault();
          history.pushState(null, "", link.hash);
          if (lenis) lenis.scrollTo(target, { offset: -24 });
          else target.scrollIntoView({ behavior: "instant", block: "start" });
        };
        element.addEventListener("click", anchorClick, true);
        const progress = ScrollTrigger.create({
          trigger: element,
          start: "top top",
          end: "bottom bottom",
          onUpdate: (self) => {
            scroll.current.progress = self.progress;
            setPageProgress(self.progress);
          },
        });
        const splits = revealHeadlines(element, !!desktop);
        const disposeSections = animateSections(element, !!desktop, !lowPower);
        const disposeAmbient = animateAmbient(element, !lowPower);
        const disposePointers = desktop && !lowPower ? animatePointers(element) : () => {};

        ScrollTrigger.refresh();
        return () => {
          disposeSections();
          disposeAmbient();
          disposePointers();
          gsap.ticker.remove(tick);
          if (desktop) gsap.ticker.lagSmoothing(500, 33);
          lenis?.off("scroll", ScrollTrigger.update);
          lenis?.destroy();
          progress.kill();
          heroProgress.kill();
          element.removeEventListener("pointermove", pointer);
          element.removeEventListener("click", anchorClick, true);
          splits.forEach((split) => split.revert());
          scroll.current.progress = 0;
        };
      }, element);
    });

    return () => {
      disposed = true;
      // matchMedia reverts only this route's animations and pins, including on resize.
      media.revert();
      element.removeAttribute("data-ambient-off");
      ScrollTrigger.getAll().forEach((trigger) => {
        if (trigger.trigger && element.contains(trigger.trigger)) trigger.kill();
      });
    };
  }, { scope: root });

  return <SceneMotionContext.Provider value={scroll}><div ref={root} className={styles.page} data-crewbie-unlocks>{children}</div></SceneMotionContext.Provider>;
}
