import type { Metadata } from "next";
import Link from "next/link";
import { ScrollStory } from "./_components/ScrollStory";
import { CrewbieLogo } from "./_components/CrewbieLogo";
import { PlanningPanel } from "./_components/PlanningPanel";
import { UnlockCTA } from "./_components/UnlockCTA";
import { UnlockSceneLoader } from "./_components/UnlockSceneLoader";
import styles from "./unlocks.module.css";

export const metadata: Metadata = {
  title: "Crewbie Unlocks — Make room for something good",
  description: "Discover student benefits and experiences, make a plan that fits your life, and optionally find a crew to go with.",
};

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
        <Link className={styles.brand} href="/unlocks" aria-label="Crewbie Unlocks home"><CrewbieLogo /><span className={styles.brandSuffix}> / unlocks</span></Link>
        <Link className={styles.navLink} href="#how-it-works">How it works <span aria-hidden="true">↗</span></Link>
      </header>

      <section className={`${styles.section} ${styles.hero}`} data-hero aria-labelledby="hero-title">
        <div className={styles.heroAtmosphere} aria-hidden="true"><div data-parallax-background><i data-blob /><i data-blob /></div></div>
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}>Student life, a little more unlocked</p>
          <h1 id="hero-title" data-headline>The AI that makes plans actually happen.</h1>
          <p className={styles.lede}>Discover something useful. Make a plan that fits. Bring a crew if you feel like it.</p>
          <UnlockCTA />
          <p className={styles.caption}>Explore the walkthrough · Built around Cubbie, your iMessage assistant</p>
        </div>
        <div className={styles.heroVisual} aria-label="Illustrative Cubbie conversation">
          <div className={styles.heroArt} data-hero-composition>
          <div className={styles.cardBackdrop} aria-hidden="true"><span data-float /><span data-float /></div>
          <div className={styles.messageCard} data-float data-tilt>
            <span className={styles.cardSheen} data-card-sheen aria-hidden="true" />
            <div className={styles.cardTop}><span className={styles.statusDot} /> A little possibility</div>
            <p className={styles.messageUser}>Two hours free tomorrow.<br />What could I do?</p>
            <p className={styles.messageReply}>Let’s find something that fits.<br />Where are you starting from?</p>
            <div className={styles.cardFooter}><span>YOUR TIME. YOUR CALL.</span><span aria-hidden="true">↗</span></div>
          </div>
          </div>
        </div>
        <div className={styles.heroFoot}><span>Starting with students at ASU</span><span>Discover ↓ Plan ↓ Maybe a crew</span></div>
      </section>

      <div className={styles.marquee} aria-label="Illustrative unlock categories">
        <p className={styles.eyebrow}>A world of possibilities · Illustrative categories</p>
        <div className={styles.marqueeWindow}><div className={styles.marqueeTrack} data-marquee-track>
          {[0, 1].map((copy) => <div className={styles.marqueeSequence} key={copy} aria-hidden={copy === 1 || undefined}>
            {["Campus", "Software", "Culture", "Travel", "Food"].map((label) => <span key={label}>{label}<i aria-hidden="true">↗</i></span>)}
          </div>)}
        </div></div>
      </div>

      <section className={styles.section} id="discover" aria-labelledby="discover-title">
        <p className={styles.eyebrow}>01 / Discover the overlooked</p>
        <h2 id="discover-title" data-headline>Your student status opens more doors.</h2>
        <p className={styles.sectionIntro}>Useful things are out there. Crewbie helps you find the ones worth your time, from included campus resources to relevant student offers.</p>
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
          <p className={styles.eyebrow}>02 / Make it fit</p>
          <h2 id="plan-title" data-headline>Start with free time. Or something in mind.</h2>
          <p className={styles.sectionIntro}>“I have two hours” and “Help me plan dinner Friday” are both good places to start.</p>
          <p className={styles.caption}>Illustrative walkthrough · No request is submitted</p>
        </div>
        <PlanningPanel />
      </section>

      <section className={`${styles.section} ${styles.details}`} aria-labelledby="details-title">
        <div><p className={styles.eyebrow}>03 / Fewer unknowns</p><h2 id="details-title" data-headline>Know what fits before you go.</h2><p className={styles.sectionIntro}>An Unlock Card puts the useful details in one conversation: why it fits, what it costs, who can access it and what to check next.</p><p className={styles.smallNote}>Original sources matter. Estimates and unanswered questions stay labeled.</p></div>
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
        <p className={styles.eyebrow}>04 / Company, when you want it</p>
        <h2 id="crew-title" data-headline>Keep the plan. Add a crew if you want.</h2>
        <p className={styles.sectionIntro}>Once you’ve chosen an activity, you can ask to find other students going to that same activity. Going solo stays a good plan, too.</p>
        <div className={styles.crewComposition} data-crew-composition>
          <article className={styles.soloCard} data-solo-card data-tilt>
            <span className={styles.cardSheen} data-card-sheen aria-hidden="true" />
            <span className={styles.eyebrow}>Your solo plan</span>
            <h3>One activity.<br />A plan that fits.</h3>
            <p>Something you want to do, within the time and budget you choose.</p>
            <span className={styles.soloTag}>Good on your own. Open to company.</span>
          </article>
          <ol className={styles.crewSteps}>
            <li data-crew-card><span>01 / Your permission</span><h3>Choose to look for company.</h3><p>Approve the activity and planning details shared for matching.</p></li>
            <li data-crew-card><span>02 / Your limits</span><h3>Find a time that fits.</h3><p>Agents negotiate within the flexibility students already authorized.</p></li>
            <li data-crew-card><span>03 / Your decision</span><h3>Accept an offer. Then say hi.</h3><p>You confirm before joining. A private Discord thread opens when a crew has at least two members.</p></li>
          </ol>
        </div>
        <p className={styles.smallNote}>The documented matching experience is still being connected. This preview does not match students or guarantee a companion.</p>
      </section>

      <section className={`${styles.section} ${styles.finale}`} aria-labelledby="final-title" data-finale>
        <p className={styles.eyebrow} data-final-reveal>A little possibility goes a long way</p>
        <h2 id="final-title" data-headline>Your next unlock starts with you.</h2>
        <p className={styles.lede} data-final-reveal>Your time, your budget, your decision.<br />Something worthwhile to do. Company is optional.</p>
        <UnlockCTA quiet />
        <p className={styles.caption} data-final-reveal>Explore the walkthrough. No signup or connected calendar needed.</p>
      </section>
      <footer className={styles.footer}><span className={styles.brand}><CrewbieLogo /></span><p>A preview of the documented Crewbie experience.<br />No booking, payment or automatic crew membership.</p><Link href="#hero-title">Back to top ↑</Link></footer>
    </ScrollStory>
  );
}
