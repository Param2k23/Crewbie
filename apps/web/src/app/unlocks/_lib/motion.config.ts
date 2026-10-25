export const motion = {
  desktop: "(min-width: 900px) and (pointer: fine) and (prefers-reduced-motion: no-preference)",
  reduced: "(prefers-reduced-motion: reduce)",
  duration: { reveal: 0.85, settle: 0.55 },
  stagger: 0.055,
  ease: { reveal: "expo.out", scroll: "none" },
  planning: { hold: 2 },
  ambient: {
    blobs: [28, 36], floats: [6, 8, 10], marquee: 32,
    glow: 3.2, shine: 1.8, shineDelay: 1.2, ease: "sine.inOut",
  },
  scene: {
    mobileSpeed: .24, floatSpeed: .75, mobileFloatSpeed: .35, floatStep: .08,
    pointerTiltX: .32, pointerTiltY: .48, pointerTravel: .5, pointerResponse: 9,
    mobileCards: 3, mobilePrimaryScale: .76, mobileSecondaryScale: .58,
  },
};
