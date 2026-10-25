import type { Metadata } from "next";
import Link from "next/link";
import { ScrollStory } from "./_components/ScrollStory";
import { CubbieLockup } from "./_components/CubbieLockup";
import { PlanningPanel } from "./_components/PlanningPanel";
import { UnlockCTA } from "./_components/UnlockCTA";
import { UnlockSceneLoader } from "./_components/UnlockSceneLoader";
import { INSTALL_MESSAGE } from "./_lib/install";
import styles from "./unlocks.module.css";

export const metadata: Metadata = {
  title: "Cubbie × Crewbie — Text Cubbie. Plans actually happen.",
  description: "Crewbie is a Skill built on Cubbie, your iMessage assistant. Text Cubbie to discover student perks, plan around your week, and find a crew if you want company.",
  openGraph: { title: "Cubbie × Crewbie", description: "Built on Cubbie. Text Cubbie, and plans actually happen." },
};

const cubbieBase = [
  ["01", "One text to install.", "Send Cubbie a link and it adds Crewbie as a Skill, asking before it fetches anything. Updates arrive the same way.", "Install"],
  ["02", "Cubbie does the legwork.", "With your permission it uses your calendar, Canvas deadlines and remembered preferences, then opens the original listings to check student eligibility and prices.", "Context and research"],
  ["03", "Cubbie keeps you in charge.", "It asks before anything is shared, texts only you, and never books, buys or joins anything without your yes.", "Consent"],
];

const categories = [
  ["01", "More campus, less guesswork.", "Recreation, library equipment, workshops and resources you might already have access to.", "On campus"],
  ["02", "Student status. Everyday value.", "Explore software, transport, dining and memberships, with eligibility and total cost checked.", "Beyond campus"],
  ["03", "A little out of the ordinary.", "Find arts, culture and local experiences that fit the time and budget you actually have.", "Around you"],
];

export default function UnlocksPage() {
  return (
    <ScrollStory>
      <UnlockSceneLoader />
      <div className={styles.scrollProgress} aria-hidden="true"><i data-page-progress /></div>
      <header className={styles.nav}>
        <Link className={styles.brand} href="/unlocks" aria-label="Cubbie and Crewbie home"><CubbieLockup /></Link>
        <Link className={styles.navLink} href="#how-it-works">How it works <span aria-hidden="true">↗</span></Link>
      </header>

      <section className={`${styles.section} ${styles.hero}`} data-hero aria-labelledby="hero-title">
        <div className={styles.heroAtmosphere} aria-hidden="true"><div data-parallax-background><i data-blob /><i data-blob /></div></div>
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}>Cubbie × Crewbie · Student life, a little more unlocked</p>
          <h1 id="hero-title" data-headline>Text Cubbie. Plans actually happen.</h1>
          <p className={styles.lede}>Crewbie is built on Cubbie, your iMessage assistant. One text to add it, then Cubbie finds student perks, plans around your week and brings a crew if you want one.</p>
          <UnlockCTA />
          <p className={styles.caption}>Everything happens in your Cubbie thread · Made for the Cubbie hackathon</p>
        </div>
        <div className={styles.heroVisual} aria-label="Illustrative Cubbie conversation">
          <div className={styles.heroArt} data-hero-composition>
          <div className={styles.cardBackdrop} aria-hidden="true"><span data-float /><span data-float /></div>
          <div className={styles.messageCard} data-float data-tilt>
            <span className={styles.cardSheen} data-card-sheen aria-hidden="true" />
            <div className={styles.cardTop}><span className={styles.statusDot} /> Cubbie · iMessage</div>
            <p className={styles.messageUser}>Two hours free tomorrow.<br />What could I do?</p>
            <p className={styles.messageReply}>Let’s find something that fits.<br />Where are you starting from?</p>
            <div className={styles.cardFooter}><span>YOUR TIME. YOUR CALL.</span><span aria-hidden="true">↗</span></div>
          </div>
          </div>
        </div>
        <div className={styles.heroFoot}><span>Starting with students at ASU</span><span>Text ↓ Plan ↓ Maybe a crew</span></div>
      </section>

      <div className={styles.marquee} aria-label="Illustrative unlock categories">
        <p className={styles.eyebrow}>A world of possibilities · Illustrative categories</p>
        <div className={styles.marqueeWindow}><div className={styles.marqueeTrack} data-marquee-track>
          {[0, 1].map((copy) => <div className={styles.marqueeSequence} key={copy} aria-hidden={copy === 1 || undefined}>
            {["Campus", "Software", "Culture", "Travel", "Food"].map((label) => <span key={label}>{label}<i aria-hidden="true">↗</i></span>)}
          </div>)}
        </div></div>
      </div>

      <section className={styles.section} id="cubbie" aria-labelledby="cubbie-title">
        <p className={styles.eyebrow}>01 / Cubbie is the base</p>
        <h2 id="cubbie-title" data-headline>Everything starts with one text to Cubbie.</h2>
        <p className={styles.sectionIntro}>Crewbie is not another app to download. It is a Skill that lives inside Cubbie, so every step happens in the iMessage thread you already use. Cubbie is the one place you talk to, and the one thing that connects the rest.</p>
        <div className={styles.categoryGrid} data-reveal-group="cubbie">
          {cubbieBase.map(([number, title, copy, tag]) => <article className={styles.category} key={number} data-reveal-card data-tilt>
            <span className={styles.cardSheen} data-card-sheen aria-hidden="true" />
            <div className={styles.categoryTop}><span>{number}</span><span>{tag}</span></div>
            <div className={styles.categoryMark} aria-hidden="true">{number}</div>
            <h3>{title}</h3><p>{copy}</p>
          </article>)}
        </div>
      </section>

      <section className={styles.section} id="discover" aria-labelledby="discover-title">
        <p className={styles.eyebrow}>02 / Discover the overlooked</p>
        <h2 id="discover-title" data-headline>Your student status opens more doors.</h2>
        <p className={styles.sectionIntro}>Useful things are out there. Ask Cubbie and it looks for student-only offers first, then everything else, so the first thing you see is the benefit you can actually use.</p>
        <div className={styles.categoryGrid} data-reveal-group="discovery">
          {categories.map(([number, title, copy, tag]) => <article className={styles.category} key={number} data-reveal-card data-tilt>
            <span className={styles.cardSheen} data-card-sheen aria-hidden="true" />
            <div className={styles.categoryTop}><span>{number}</span><span>{tag}</span></div>
            <div className={styles.categoryMark} aria-hidden="true">{number}</div>
            <h3>{title}</h3><p>{copy}</p>
          </article>)}
        </div>
      </section>

      <section className={`${styles.section} ${styles.plan}`} id="how-it-works" data-plan aria-labelledby="plan-title">
        <div className={styles.planHeading}>
          <p className={styles.eyebrow}>03 / Make it fit</p>
          <h2 id="plan-title" data-headline>Start with free time. Or something in mind.</h2>
          <p className={styles.sectionIntro}>Text Cubbie like you would a friend. “I have two hours” and “Help me plan dinner Friday” are both good places to start.</p>
          <p className={styles.caption}>Illustrative walkthrough · Nothing is sent to Cubbie from this page</p>
        </div>
        <PlanningPanel />
      </section>

      <section className={`${styles.section} ${styles.details}`} aria-labelledby="details-title">
        <div><p className={styles.eyebrow}>04 / Fewer unknowns</p><h2 id="details-title" data-headline>Know what fits before you go.</h2><p className={styles.sectionIntro}>Cubbie sends an Unlock Card right in your thread: why it fits, what it costs, who can access it and what to check next.</p><p className={styles.smallNote}>Original sources matter. Estimates and unanswered questions stay labeled.</p></div>
        <article className={styles.unlockCard} aria-labelledby="example-title" data-reveal-group="details" data-tilt>
          <span className={styles.cardSheen} data-card-sheen aria-hidden="true" />
          <div className={styles.cardTop}>EXAMPLE UNLOCK <span aria-hidden="true">↗</span></div>
          <h3 id="example-title">An evening around a board-game table.</h3>
          <p className={styles.caption}>Illustrative activity · Not a verified event listing</p>
          <dl>
            <div data-reveal-card><dt>Why it fits</dt><dd>A relaxed option to explore in your free window.</dd></div>
            <div data-reveal-card><dt>Access & cost</dt><dd>Student eligibility, fees and availability need checking.</dd></div>
            <div data-reveal-card><dt>Time & travel</dt><dd>Confirm the date, venue and return journey before deciding.</dd></div>
            <div data-reveal-card><dt>Next step</dt><dd>Check the organizer’s original listing and participation requirements.</dd></div>
          </dl>
        </article>
      </section>

      <section className={`${styles.section} ${styles.crew}`} aria-labelledby="crew-title">
        <p className={styles.eyebrow}>05 / Company, when you want it</p>
        <h2 id="crew-title" data-headline>Keep the plan. Add a crew if you want.</h2>
        <p className={styles.sectionIntro}>Once you’ve chosen an activity, Cubbie can ask whether you want to find other students going to it. You say yes first, and going solo stays a good plan.</p>
        <div className={styles.crewComposition} data-crew-composition>
          <article className={styles.soloCard} data-solo-card data-tilt>
            <span className={styles.cardSheen} data-card-sheen aria-hidden="true" />
            <span className={styles.eyebrow}>Your solo plan</span>
            <h3>One activity.<br />A plan that fits.</h3>
            <p>Something you want to do, within the time and budget you choose.</p>
            <span className={styles.soloTag}>Good on your own. Open to company.</span>
          </article>
          <ol className={styles.crewSteps}>
            <li data-crew-card><span>01 / Your permission</span><h3>Cubbie lists what is shared.</h3><p>It names exactly what goes to Crewbie, what stays private, and waits for your yes.</p></li>
            <li data-crew-card><span>02 / Your limits</span><h3>Agents work within your limits.</h3><p>Your private agent answers small time changes inside the flexibility you gave. Those limits are stored encrypted and never shown to anyone.</p></li>
            <li data-crew-card><span>03 / Your decision</span><h3>Say yes. Then say hi.</h3><p>Cubbie asks “Join?” and nothing happens until you answer. A private Discord thread opens once a crew has two members, and Cubbie keeps you posted.</p></li>
          </ol>
        </div>
        <p className={styles.smallNote}>Crew matching is live in preview for students using the Crewbie Skill with Cubbie. A companion is never guaranteed.</p>
      </section>

      <section className={`${styles.section} ${styles.finale}`} aria-labelledby="final-title" data-finale>
        <p className={styles.eyebrow} data-final-reveal>Cubbie × Crewbie</p>
        <h2 id="final-title" data-headline>Your next unlock is one text away.</h2>
        <p className={styles.lede} data-final-reveal>Your time, your budget, your decision.<br />Cubbie does the legwork. Company is optional.</p>
        <div className={styles.install} data-final-reveal>
          <p className={styles.eyebrow}>Text this to Cubbie</p>
          <code className={styles.installCode}>{INSTALL_MESSAGE}</code>
          <p className={styles.caption}>Cubbie shows the repository and asks before it installs. No signup, and no connected account needed.</p>
        </div>
      </section>
      <footer className={styles.footer}><span className={styles.brand}><CubbieLockup /></span><p>Built on Cubbie for the Cubbie hackathon.<br />No booking, payment or automatic crew membership.</p><Link href="#hero-title">Back to top ↑</Link></footer>
    </ScrollStory>
  );
}
