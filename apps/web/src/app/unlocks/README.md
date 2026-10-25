# Crewbie Unlocks

From `apps/web`, run `npm run dev` and open `http://localhost:3000/unlocks`.
For a production preview, run `npm run build`, then `npm start`.

The acts are server-rendered in `page.tsx`. The page is "Cubbie x Crewbie": Cubbie, the
iMessage assistant, is presented as the base and the single connection point, and Crewbie as the
Skill built on it. Every claim must be something the Skill really does (see
`skills/crewbie-unlocks/SKILL.md`); `tests/unlocks-page.test.tsx` guards the key wording and that
the install message points at the real Skill folder. Conversations and the Unlock Card are
illustrative and labeled as such. The install message lives in `_lib/install.ts`.

`CubbieLockup.tsx` draws "Cubbie" as a text wordmark next to the Crewbie logo. If the Cubbie team
supplies an official logo, replace the wordmark in that one file.

Routes: `/` redirects to `/unlocks` (see `next.config.mjs`). The Mission Control demo stays at
`/demo` (Campus Pulse) and `/arena`.

Tokens and responsive layouts live in `unlocks.module.css`. Its `:has()` selector
hides only the inherited header while this route's marker is present. The root
layout and shared navigation are unchanged.

The logo search found no standalone brand asset in `apps/web`; the existing demo
navigation uses a CSS gradient dot (`SiteNav.tsx` and `.brand-dot` in `globals.css`).
The two new flat inline SVG placeholders live in `_components/CrewbieLogo.tsx`:
`unlock` is a rounded keyhole card, and `cards` is three overlapping rounded squares.
Change `defaultVariant` from `"unlock"` to `"cards"` to swap both wordmarks.
The monochrome route favicon uses the unlock motif.

The earlier route orange was custom, rather than the repo's exact accent token.
The new electric-blue accent is `--accent` in `unlocks.module.css`. Every route
color is declared there; SVGs inherit `currentColor`. The wordmark uses `--display`.

Animation timings and media queries live in `_lib/motion.config.ts`.
`_components/ScrollStory.tsx` owns the GSAP context, Lenis ticker callback,
SplitText instances, page/hero progress and the instance-local scene motion ref.
Desktop fine pointers use Lenis on the GSAP ticker, with milliseconds conversion
and lag smoothing disabled. Touch and narrow screens use native scrolling and
light opacity reveals. Reduced motion skips animation entirely.
Media changes and route unmounts revert the route's effects and remove Lenis.

Act 3 has no pin or scrub. `PlanningPanel.tsx`, `planningAnimation.ts` and
`planningExamples.ts` define three illustrative request/checks/plan examples. A
time-based timeline reveals lines, draws check marks, highlights numbers and fills
connectors, holds for two seconds, then replays the next example. It pauses outside
the viewport or in hidden tabs. Reduced motion keeps all three steps static.

`sectionAnimations.ts` owns headline/card reveals and layered desktop parallax.
`ambientAnimations.ts` owns drifting blobs, floating UI, marquee, CTA glow and shine.
`pointerAnimations.ts` owns desktop card tilt/sheen and magnetic CTAs. The only
entrance eases are `expo.out` and `none`, with 0.85s/0.55s durations. Ambient timings
are separately defined in `motion.config.ts`. All continuous motion pauses off-screen
and in hidden tabs, and is disabled when `hardwareConcurrency <= 4` or reduced
motion is requested. Low-power devices play the planning timeline once.

`UnlockSceneLoader.tsx` waits until after first paint to load `UnlockScene.tsx`
through a client-only dynamic import. The initial route does not import Three.
Six procedural RoundedBox cards use locally drawn illustrative canvas textures,
physical materials and a generated lighting environment. Scroll progress and
pointer coordinates are mutable refs; `useFrame` damps transforms without React
updates per tick. Desktop cards converge on scroll. Mobile uses a compact three-card
composition with light floating motion. The HTML conversation and CSS backplates are hidden once the 3D
scene is ready in either layout, and remain available as the fallback
for reduced motion, low-power devices, loading, renderer failure or context loss.
The transparent fixed canvas is decorative, ignores pointer events, uses DPR 1–1.5,
and stops its render loop outside the hero or in a hidden tab. PerformanceMonitor
lowers DPR to 1 on drops. Data attributes on the route report draw calls, frames
and DPR for browser verification. Canvas textures are explicitly disposed; R3F
owns and releases the declared geometries, materials, root renderer and canvas,
and drei releases its generated environment render target.

The accent and texture palette come from `unlocks.module.css`. Change example
labels in `UnlockScene.tsx`; tune texture typography in `cardTextures.ts`. No
external model, HDRI, font request or stock assets are required. Target fewer
than 100 draw calls and initial JS below approximately 200 KB gzipped.

After a production build, measure the exact gzip totals with
`node src/app/unlocks/_checks/measure-bundles.mjs`. The report distinguishes the
initial route (including shared runtime) from the complete deferred 3D group.
For browser verification, start a production server on port 3100 and run
`node src/app/unlocks/_checks/verify.mjs`. It uses the installed Playwright and
Microsoft Edge; captures are written to the system temporary directory.

Known dependency compatibility issue: installed R3F 9.8.2 creates `THREE.Clock`,
which installed Three 0.186.1 deprecates. The app does not suppress this warning.
Resolving it requires an approved dependency change outside this route. The
browser check reports this upstream warning separately from application errors.
