// Changelog — a plain-language, newest-first log of what's shipped. Static (no
// data, no client state) so it prerenders. Lives in the nav for guests and moves
// to the footer once you're in an account (see components/nav.tsx + footer).

import type { Metadata } from "next";
import Link from "next/link";
import { MarkerText } from "@/components/marker-text";

export const metadata: Metadata = {
  title: "Changelog",
  description: "What's new in DECK — newest changes first.",
};

function Entry({
  date,
  title,
  children,
}: {
  date: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-8 border-l-2 border-line pl-5">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">
        {date}
      </p>
      <h2 className="mt-1 font-display text-xl font-bold tracking-tight">
        {title}
      </h2>
      <ul className="mt-2 list-disc space-y-1.5 pl-5 text-[0.95rem] leading-relaxed text-ink/80">
        {children}
      </ul>
    </section>
  );
}

export default function ChangelogPage() {
  return (
    <div className="mx-auto max-w-2xl px-5 py-12 sm:px-8">
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← Back home
      </Link>

      <div className="mt-4">
        <MarkerText rotate={-3} className="text-base">
          what&rsquo;s new
        </MarkerText>
        <h1 className="mt-1 font-display text-4xl font-extrabold tracking-tight sm:text-5xl">
          Changelog
        </h1>
        <p className="mt-3 text-sm text-muted">
          DECK is in active beta. Here&rsquo;s what&rsquo;s changed lately, newest
          first — expect frequent updates.
        </p>
      </div>

      <Entry
        date="August 2026"
        title="The rest of the question bank is now browsable"
      >
        <li>
          <strong>New &ldquo;Extra pool&rdquo; shelf in the question bank.</strong>{" "}
          Pick a cluster and you&rsquo;ll now see it under the numbered sets. It holds
          every question we&rsquo;ve written for that cluster that never went into a
          numbered exam set &mdash; about 13,000 questions across the five clusters,
          which until now you could only meet through a generated test.
        </li>
        <li>
          <strong>Filter it down to what you&rsquo;re actually studying.</strong>{" "}
          Narrow a pool by instructional area or difficulty, or search the question
          text, the performance indicator, and the answer choices. Results come 20 to
          a page.
        </li>
        <li>
          <strong>Quiz yourself on whatever the filter leaves.</strong>{" "}
          One button draws a random 20 from your current filter and runs them as a
          focus quiz, the same way a set does.
        </li>
        <li>
          Like the rest of the question bank, it works signed out &mdash; an account
          is only what records your answers.
        </li>
      </Entry>

      <Entry
        date="August 2026"
        title="Human Resources Management roleplays added"
      >
        <li>
          <strong>30 new Human Resources Management Series roleplays.</strong>{" "}
          It&rsquo;s the second event with a full set, after Business Law and
          Ethics. Same 10 minutes of prep and 10 to present as the real thing,
          with the performance indicators and 21st Century Skills laid out the way
          DECA lays them out.
        </li>
        <li>
          <strong>They&rsquo;re actually about HR.</strong>{" "}
          Every event lists several instructional areas a case can be built
          around, and until now we picked between them evenly &mdash; which meant
          a Human Resources event kept handing you customer-service and economics
          indicators. We now pick the way DECA does, counting how often each area
          shows up across 19 years of real HRM cases. Hiring, pay, scheduling,
          reviews and workplace conduct now carry the set.
        </li>
        <li>
          <strong>Nothing off-topic slipped in.</strong>{" "}
          The old approach could pull an indicator about hotels or retail
          merchandising into an HR case. None of the 30 has one.
        </li>
        <li>
          Situations run about 320 words, close to what DECA prints for this event
          now.
        </li>
      </Entry>

      <Entry
        date="August 2026"
        title="Business Law &amp; Ethics roleplays rewritten"
      >
        <li>
          <strong>Two thirds of the Business Law and Ethics Team Decision Making
          roleplays are new.</strong>{" "}
          An outside review of the old set found
          problems in most of them &mdash; performance indicators the situation
          gave you no way to actually demonstrate, and cases where one of the two
          choices was so obviously wrong there was nothing left to decide. Those
          20 were thrown out and written again from scratch. The 10 that came
          through the review clean were left alone.
        </li>
        <li>
          <strong>Nothing gets patched up any more.</strong>{" "}
          A roleplay that
          fails our quality checks is discarded and rewritten, never edited into
          shape. Three of the new ones failed on the first pass and were rewritten
          before anything reached you.
        </li>
        <li>
          <strong>Situations are shorter.</strong>{" "}
          The old ones ran long against
          the length real DECA materials use now. The new ones sit close to it, so
          the reading load in your 30 minutes of prep is closer to the real thing.
        </li>
        <li>
          The other 27 events are unchanged for now &mdash; Business Law and
          Ethics went first, and the rest follow once these read right.
        </li>
      </Entry>

      <Entry
        date="August 2026"
        title="The privacy page now names everything your account stores"
      >
        <li>
          The <strong>Privacy</strong>{" "}
          page listed two things kept against an
          account &mdash; your username and your practice log. It kept more than
          that, and now says so: your <strong>study plan</strong> (the cluster and
          level you&rsquo;re aiming at, the <strong>competition date you
          enter</strong>, and today&rsquo;s tasks), the avatar emoji you pick, and
          a <strong>sign-in token</strong> that keeps one account to one device at
          a time.
        </li>
        <li>
          It also now says that once you&rsquo;re signed in, a copy of your
          practice log and plan is kept <strong>in your browser on the device
          you&rsquo;re using</strong>{" "}
          &mdash; that&rsquo;s what makes DECK fast and
          keeps it working if your connection drops. <strong>Delete account</strong>{" "}
          removes that copy along with everything else.
        </li>
        <li>
          <strong>Nothing about the app changed</strong>{" "}
          and nothing new is being
          collected. This was always what DECK stored; the page just hadn&rsquo;t
          spelled it out. Guest mode is unaffected &mdash; it still keeps no
          record of your practice anywhere.
        </li>
      </Entry>

      <Entry
        date="August 2026"
        title="Reset progress now clears the day’s plan too"
      >
        <li>
          Resetting your progress used to wipe your answered questions and
          sessions but leave <strong>today’s plan</strong> standing — so the
          dashboard kept showing the same task cards, and pressing Start handed
          you the exact same questions back. Reset now clears the day’s plan
          with the rest of it, and a fresh plan is built for you.
        </li>
        <li>
          Your <strong>target event, level and competition date are kept</strong>{" "}
          — a reset clears your practice, not your setup, so you don’t have to
          go through the first-run questions again.
        </li>
        <li>
          Fixed alongside it: a task resumed after a reset logged its answers
          against a session that no longer existed, so Progress showed the
          questions but <strong>no session and no readiness point</strong> for
          them. Those sittings are now recorded properly.
        </li>
      </Entry>

      <Entry
        date="August 2026"
        title="The footer links stop pushing every page sideways on a phone"
      >
        <li>
          Once you were signed in, the row of links at the bottom of the page
          &mdash; Practice Tests, Roleplays, Changelog, Help, Terms and Privacy
          &mdash; couldn&rsquo;t break onto a second line, so on a phone it pushed
          the whole page out past the edge. <em>Practice Tests</em> ran off the
          left and <em>Privacy</em>{" "}
          was cut off on the right, where you
          couldn&rsquo;t tap it, and every page slid sideways as you scrolled. It
          was worst on a small phone and it happened everywhere, not on one page.
        </li>
        <li>
          That row now wraps, so the links stack neatly in the middle and the page
          fits the screen. Nothing changed on a tablet or a laptop, where they
          already fit on one line.
        </li>
      </Entry>

      <Entry
        date="August 2026"
        title="Business Law and Ethics roleplays, rebuilt at ICDC level"
      >
        <li>
          The roleplay bank was emptied and is being rebuilt from scratch. The
          first event back is{" "}
          <strong>Business Law and Ethics Team Decision Making</strong>, which
          now has <strong>30 case studies</strong>{" "}
          written to match DECA&rsquo;s
          real ICDC format &mdash; a case study situation, the 21st Century
          Skills block, seven performance indicators, and two judge questions,
          for a two-person team with 30 minutes of prep and 15 to present.
        </li>
        <li>
          Every case is built around a decision with{" "}
          <strong>two defensible answers</strong>, not a right one and a wrong
          one. There are no exhibits and no math to work through &mdash; the
          judging is on how you reason and present, the same as the real thing.
        </li>
        <li>
          Other events are still empty while this format gets checked, so
          you&rsquo;ll see most of the roleplay board greyed out for now.
          They&rsquo;re coming.
        </li>
        <li>
          As always, these are <strong>written by AI and some of it is
          wrong</strong>{" "}
          &mdash; they&rsquo;re practice, not official DECA
          material.
        </li>
      </Entry>

      <Entry date="August 2026" title="A Terms page, in plain English">
        <li>
          DECK now has a <strong>Terms</strong>{" "}
          page to go with the privacy
          policy, written the same way &mdash; plain language, meant to be
          readable by a parent. You&rsquo;ll find it in the footer at the bottom
          of any page, next to Privacy.
        </li>
        <li>
          It says out loud what the app was only implying: every question,
          roleplay, and vocab term here is <strong>written by AI, so some of it
          is wrong</strong>, and none of it is official DECA preparation. It also
          covers who can make an account (13 or older), how an account can be
          closed by you or by us, the fact that there&rsquo;s still no password
          reset, and that DECK is a free beta that can change or go offline. Data
          questions stay on the privacy page, which the new page links to rather
          than repeating.
        </li>
        <li>
          The sign-up form now says <em>&ldquo;By creating an account you agree
          to the Terms and Privacy policy&rdquo;</em>, with both links, so
          you&rsquo;re not agreeing to something you can&rsquo;t see. Nothing
          about how you sign up changed &mdash; it&rsquo;s the same one checkbox
          as before.
        </li>
      </Entry>

      <Entry
        date="August 2026"
        title="A &ldquo;Learn&rdquo; drill now says when it borrowed from nearby topics"
      >
        <li>
          A <strong>Learn</strong>{" "}
          card on your daily plan practices one performance
          indicator. Some indicators only have two questions in the bank, so a card
          asking for three quietly filled the last slot from elsewhere in the same
          topic &mdash; and said nothing. You&rsquo;d answer a question filed under a
          heading it didn&rsquo;t match.
        </li>
        <li>
          Those drills now say so: <em>Topped up from the wider area &mdash; some
          questions are from other indicators.</em>{" "}
          The questions you get haven&rsquo;t changed &mdash; only whether
          you&rsquo;re told. A drill served entirely from the named indicator still
          says nothing, and a drill with no questions on that indicator at all keeps
          its own existing note.
        </li>
      </Entry>

      <Entry
        date="August 2026"
        title="The Roleplay Challenge stops scrolling sideways on a phone"
      >
        <li>
          On a phone, the <strong>Roleplay Challenge</strong>{" "}
          board was wider than
          the screen. The three day controls at the top &mdash; Previous day, Next
          day, and Browse the archive &mdash; sat in a row that couldn&rsquo;t break
          onto a second line, so they pushed the whole page out past the edge. Half
          of <em>Browse the archive</em> was off-screen, everything else looked
          off-centre with a dead strip down the right, and the page slid sideways as
          you scrolled.
        </li>
        <li>
          That row now wraps, so the controls stack on a narrow screen and the board
          fits. Opening a scenario is fixed with it &mdash; it was being sized
          against the too-wide page, so its panel hung off the screen too. Nothing
          changed on a tablet or a laptop, where all three already fit on one line.
        </li>
      </Entry>

      <Entry
        date="August 2026"
        title="Dashboard drills now tell you when they had to widen the net"
      >
        <li>
          Tapping <strong>Practice this</strong>{" "}
          on a performance indicator normally
          serves questions on exactly that indicator. Occasionally we don&rsquo;t
          have any &mdash; usually one you practiced before we rewrote that part of
          the question bank &mdash; so we serve questions from the surrounding topic
          instead. The Progress page has always said so; the dashboard said nothing,
          and you&rsquo;d get ten questions filed under a heading they didn&rsquo;t
          match.
        </li>
        <li>
          Now both pages say the same thing: <em>Closest available &mdash; practicing
          the whole area.</em>{" "}
          Your daily plan&rsquo;s drills say it too. The
          questions you get haven&rsquo;t changed &mdash; only whether you&rsquo;re
          told which ones they are.
        </li>
      </Entry>

      <Entry
        date="August 2026"
        title="The &ldquo;we couldn&rsquo;t save that&rdquo; warning stops hiding behind the quiz"
      >
        <li>
          If your browser blocks DECK from saving on this device &mdash; private
          browsing and a full disk are the usual reasons &mdash; or if something
          can&rsquo;t reach your account, we put a note at the bottom of the screen
          telling you so. But both of those only happen while you&rsquo;re
          answering questions, and the quiz screen was painting right over the
          note. You&rsquo;d work through the whole set seeing nothing and only find
          out on the way out.
        </li>
        <li>
          Now the note shows up <strong>on top of the quiz</strong>, where it can
          be read, dismissed with the keyboard, and read aloud by a screen reader.
          Same for the settings window. Nothing about what gets saved has changed
          &mdash; only whether you find out when it doesn&rsquo;t.
        </li>
      </Entry>

      <Entry date="August 2026" title="Practice history stops double-counting a quiz">
        <li>
          If you finished a quiz, pressed <strong>Review answers</strong>, and then
          filled in a question you&rsquo;d skipped, that quiz was being saved twice
          — as two separate sessions on your Progress page. The second one claimed
          every answer from the whole run even though it only held the one you
          just added, so the score and the little difficulty dots beside it
          disagreed with each other.
        </li>
        <li>
          Now that&rsquo;s one quiz, one row, with the counts it actually earned.
          Your readiness graph also stops showing an extra point for it. Starting
          a <strong>New set</strong>{" "}
          still counts as a new quiz, as you&rsquo;d expect. Sessions already
          saved this way are left as they are.
        </li>
      </Entry>

      <Entry date="August 2026" title="The last of the hospitality giveaways are gone">
        <li>
          Twice before we&rsquo;ve written about hospitality questions that were{" "}
          <strong>describing their own answers</strong> — where each of the four
          choices explained how its number was worked out, so you could pick the
          right one by reading instead of doing the maths. We went back for the
          rest. <strong>Every remaining one is rewritten</strong> — 79 questions
          across all three hospitality levels. Same questions, same numbers, same
          right answer; the choices just say what the number <em>is</em> now.
        </li>
        <li>
          While we were in there we checked whether the rewrite had swapped one
          giveaway for another — and it had. The correct answer had ended up{" "}
          <strong>never the longest and never the shortest</strong>{" "}
          choice, on
          every single one, which is its own kind of hint. That&rsquo;s fixed
          too: answer length is now spread the same way it is everywhere else in
          the bank, so it tells you nothing.
        </li>
        <li>
          We also found four questions whose <strong>explanation was wrong about
          a wrong answer</strong> — it said a choice came from doubling one
          figure when that choice was actually double a different one. Those are
          the sentences you read right after you miss a question, so they matter
          more than most. All four are corrected.
        </li>
        <li>
          Nothing you&rsquo;ve already answered was affected: your history, your
          scores and your error log all still point at the same questions.
        </li>
      </Entry>

      <Entry date="August 2026" title="Your study plan stops losing changes on a bad connection">
        <li>
          Changes to your daily plan — starting a task, adding one, dismissing
          one, setting your target — are saved to your account. If that save
          failed (patchy wi-fi, a hiccup on our side), the change looked fine
          until you reloaded, and then <strong>quietly reverted</strong>: a task
          you&rsquo;d worked through went back to <strong>0</strong>, and pressing
          Start again drew a brand-new set of questions instead of picking up
          where you left off.
        </li>
        <li>
          Now the change is kept on your device and{" "}
          <strong>re-sent automatically</strong> — right away, and again when you
          reconnect or come back to the tab. Reloading no longer throws it away.
        </li>
        <li>
          If it still can&rsquo;t save after several tries, you&rsquo;ll see a
          note saying so, instead of nothing at all. Your answers were never
          affected — those already had this protection.
        </li>
      </Entry>

      <Entry date="August 2026" title="A much deeper marketing question bank — and every cluster is now finished">
        <li>
          Marketing is the biggest cluster on DECK, and it went from about 1,200
          questions to over <strong>3,300</strong>. <strong>District,
          Association and ICDC</strong>{" "}
          are all done, so you can practise the
          same way at whichever level you&rsquo;re competing at.
        </li>
        <li>
          The point isn&rsquo;t the number. Every marketing performance
          indicator now has enough behind it to actually revise with, at each
          difficulty — so a <strong>Practice this PI</strong> drill from your
          mastery heatmap can start you easy and build up, instead of running
          dry after two questions or handing you the same one twice.
        </li>
        <li>
          Marketing was the last one. <strong>All five clusters</strong> —
          finance, business management, hospitality, entrepreneurship and
          marketing — are now filled out to the same depth, which puts the whole
          site past <strong>16,000</strong> questions.
        </li>
        <li>
          Every question written to be hard is checked by two independent
          reviewers plus two more who try to answer it cold, and anything that
          turns out to be a medium question in disguise gets relabelled. In this
          final marketing batch <strong>none of the nine kept the hard
          badge</strong>{" "}
          — both reviewers agreed each one was really a
          single-formula calculation. They&rsquo;re still good questions and
          they&rsquo;re all in the bank; they just sit in the medium pile, because
          a &ldquo;hard&rdquo; badge should mean something.
        </li>
      </Entry>

      <Entry date="August 2026" title="Anonymous visitor counts">
        <li>
          DECK now counts <strong>page visits</strong>{" "}
          — how many people open the
          site and which pages they use — so we can tell what&rsquo;s worth
          building next. It runs whether or not you&rsquo;re signed in.
        </li>
        <li>
          It uses <strong>no cookies</strong>, doesn&rsquo;t follow you to other
          sites, and is kept completely separate from your account and your
          practice history. Your answers are still yours alone. The{" "}
          <Link href="/privacy" className="underline underline-offset-2">
            privacy page
          </Link>{" "}
          spells out exactly what it does and doesn&rsquo;t see.
        </li>
      </Entry>

      <Entry date="August 2026" title="A much deeper entrepreneurship question bank">
        <li>
          The entrepreneurship bank went from about 1,200 questions to over{" "}
          <strong>3,200</strong>. District, Association and ICDC are all
          finished, so you can practise the same way at whichever level
          you&rsquo;re competing at.
        </li>
        <li>
          As with the other clusters, the point wasn&rsquo;t the count. Every
          entrepreneurship performance indicator now has enough behind it to
          actually review with, at each difficulty — so a{" "}
          <strong>Practice this PI</strong> drill from your mastery heatmap can
          start you easy and work up, instead of running dry after two questions
          or handing you the same one twice.
        </li>
        <li>
          Every question written to be hard is checked by two independent
          reviewers plus two more who try to answer it cold, and anything that
          turns out to be a medium question in disguise gets relabelled. In the
          last batch, 6 of 19 kept the hard badge. The other 13 are still good
          questions — they just sit in the medium pile now, because a
          &ldquo;hard&rdquo; badge should mean something.
        </li>
        <li>
          <strong>One thing the review caught this time.</strong>{" "}
          When you miss
          a question, we show you not just the right answer but why each wrong
          choice is wrong. On three questions that write-up didn&rsquo;t add up
          — it named a mistake that wouldn&rsquo;t actually produce the wrong
          number it was explaining. So a student checking their working would
          have been sent in circles. All three are rewritten, and every wrong
          choice&rsquo;s explanation now reproduces its own number.
        </li>
        <li>
          One more: a contribution-margin question described a packaging cost in
          a way that could be read either as a monthly overhead or as a
          per-batch cost — and the two readings led to different answers, both
          of which were on the list. It&rsquo;s reworded so only one reading is
          possible. Same right answer as before.
        </li>
        <li>
          Four clusters done — finance, Business Admin Core, hospitality and
          entrepreneurship. Marketing is last.
        </li>
      </Entry>

      <Entry date="August 2026" title="27 Business Administration questions that no practice test could reach">
        <li>
          27 questions in the Business Administration Core bank were filed under
          an instructional area that belongs to the Finance cluster, not this
          one. Because practice tests are built area by area, that put them
          somewhere no Business Administration test could ever pick them up —
          they were in the bank, but unreachable.
        </li>
        <li>
          They&rsquo;re now filed under <em>Financial Analysis</em>, where their
          content belongs, so they turn up in generated tests and quizzes like
          every other question. Nothing was added or removed; the wording,
          answers and explanations are untouched.
        </li>
        <li>
          On your mastery heatmap this also clears out a{" "}
          <em>Financial-Information Management</em> row that only ever showed 0%
          for Business Administration, because no practice test could fill it.
          Its three skills moved into the Financial Analysis row with the
          questions.
        </li>
      </Entry>

      <Entry date="August 2026" title="The &ldquo;thin hard shelf&rdquo; heads-up now knows what you&rsquo;re drawing from">
        <li>
          On the Practice Test builder you can pick{" "}
          <em>Pool only</em>{" "}
          — the questions that aren&rsquo;t in any numbered
          exam set. When you paired that with the <em>Challenge</em> mix, the
          heads-up that warns you a cluster is thin on hard questions stayed
          quiet, because it was counting the hard questions in the exam sets{" "}
          <strong>as well as</strong> the pool — and the exam sets were never
          going to be in your test.
        </li>
        <li>
          It now counts only what your test will actually draw from. Two setups
          gained the warning they should always have had: Entrepreneurship at
          ICDC and at District, on <em>Pool only</em> with{" "}
          <em>Challenge</em>. The tests themselves never changed — the first
          draw was always correct — but pressing <em>New set</em> there
          reshuffles a small stack of hard questions, and now the page says so.
        </li>
      </Entry>

      <Entry date="August 2026" title="&ldquo;Weak-area drill&rdquo; stopped being greyed out on good students">
        <li>
          On your daily plan, <em>Add a task → Weak-area drill</em>{" "}
          could grey itself out and tell you there was nothing to drill — even
          though there was. It happened once you&rsquo;d practised enough that no area was
          under 60%, or once today&rsquo;s plan had already claimed your weakest
          spots. Adding the drill would have worked fine; only the menu thought
          otherwise.
        </li>
        <li>
          The option is now available whenever a drill can actually be built, and
          it picks the weakest area today&rsquo;s plan hasn&rsquo;t already
          taken. The old message told you to practise more so weak areas would
          &ldquo;surface&rdquo;, which was exactly the wrong advice for someone
          who had been practising; it now says plainly that today&rsquo;s plan
          already covers what you&rsquo;ve worked on.
        </li>
      </Entry>

      <Entry date="August 2026" title="Your stats no longer mention skipped questions">
        <li>
          Your error log said it collected every question you got wrong{" "}
          <strong>or skipped</strong>, and your progress page counted skips next
          to your accuracy. Neither was true: pressing{" "}
          <em>Skip question</em>{" "}
          in a quiz simply moves you to the next one and
          records nothing at all, so the skip count sat at zero forever and the
          &ldquo;skipped&rdquo; group in the error log was always empty.
        </li>
        <li>
          We&rsquo;ve made the app say what it actually does. Skipping still
          works exactly as before — it moves you on, and you can come back to the
          question later and answer it normally — but nothing claims to be
          tracking it any more. Your answers, accuracy and error log are
          unchanged.
        </li>
        <li>
          Worth knowing: because a skipped question isn&rsquo;t answered, it
          doesn&rsquo;t count toward finishing a task on your study plan. Reopen
          the task and you&rsquo;ll land back on the questions you left.
        </li>
      </Entry>

      <Entry date="August 2026" title="Some questions were giving themselves away">
        <li>
          Last month we mentioned fixing a batch of hospitality questions that
          were <strong>describing their own answers</strong> — where the four
          choices each explained how their number was worked out, so you could
          pick the right one by reading instead of doing the maths. We went
          looking for the rest of them.
        </li>
        <li>
          We found <strong>32 more</strong>, mostly hospitality with a few in
          finance and marketing, and the worst kind: two or three of the wrong
          choices openly admitted they were wrong (&ldquo;$300, mistakenly
          applying a 15% rate&rdquo;), so you could cross them off without
          knowing anything and land on the answer. All 32 are rewritten. Same
          questions, same numbers, same right answer — the choices just
          don&rsquo;t hand it to you any more, and the reasoning has moved into
          the explanation you see after you answer.
        </li>
        <li>
          One of them was worse than a giveaway: the correct answer to an
          average-daily-rate question was labelled with the formula for a
          completely different measure. If you read that choice carefully you
          learned the wrong formula. That&rsquo;s fixed too.
        </li>
        <li>
          Nothing you&rsquo;ve already answered was lost or re-scored, and your
          error log still points at the same questions — we only changed the
          wording of the choices.
        </li>
      </Entry>

      <Entry date="August 2026" title="A much deeper hospitality question bank">
        <li>
          The hospitality bank went from about 1,200 questions to over{" "}
          <strong>3,000</strong>. District, Association and ICDC are all
          finished, so you can practise the same way at whichever level
          you&rsquo;re competing at.
        </li>
        <li>
          As with the other clusters, the point wasn&rsquo;t the count. Every
          hospitality performance indicator now has enough behind it to actually
          review with, at each difficulty — so a{" "}
          <strong>Practice this PI</strong> drill from your mastery heatmap can
          start you easy and work up, instead of running dry after two questions
          or handing you the same one twice.
        </li>
        <li>
          Every question written to be hard is checked by two independent
          reviewers plus two more who try to answer it cold, and anything that
          turns out to be a medium question in disguise gets relabelled. Across
          hospitality that was more than three quarters of them. They&rsquo;re
          still good questions — they just sit in the medium pile now, because a
          &ldquo;hard&rdquo; badge should mean something.
        </li>
        <li>
          <strong>One thing the review caught this time.</strong>{" "}
          Some of the new
          hospitality questions were describing their own answers — the four
          choices explained how each number was worked out, so you could spot the
          right one by reading carefully instead of actually doing the maths. We
          rewrote them, then had someone try to solve them by reading alone
          again to check it worked.
        </li>
        <li>
          Three clusters done — finance, Business Admin Core and hospitality.
          Marketing and entrepreneurship are next.
        </li>
      </Entry>

      <Entry
        date="July 2026"
        title="A much deeper Business Administration Core bank"
      >
        <li>
          The Business Admin Core bank went from about 1,290 questions to over{" "}
          <strong>3,000</strong>. District, Association and ICDC all grew — and
          unlike last time, all three are finished, so you can practise the same
          way at whichever level you&rsquo;re competing at.
        </li>
        <li>
          The point wasn&rsquo;t just more questions. Every performance indicator
          in the cluster now has enough behind it to actually review with. Before,
          plenty of PIs had one or two questions in total, so a{" "}
          <strong>Practice this PI</strong> drill from your mastery heatmap ran
          dry almost immediately, or handed you the same question twice.
        </li>
        <li>
          Each PI is filled at every difficulty too, so a drill can start you easy
          and work up instead of throwing whatever it happens to have at you.
        </li>
        <li>
          As with finance, every question written to be hard is checked by two
          independent reviewers plus two more who try to answer it cold, and
          anything that turns out to be a medium question in disguise gets
          relabelled. On this batch that was two thirds of them — they&rsquo;re
          still good questions, they just sit in the medium pile now. A
          &ldquo;hard&rdquo; badge should mean something.
        </li>
        <li>
          Finance and Business Admin Core are both done. Marketing,
          entrepreneurship and hospitality are next.
        </li>
      </Entry>

      <Entry date="July 2026" title="Roleplays you can actually run">
        <li>
          <strong>Scenarios open now.</strong>{" "}
          Tap any event on the day&rsquo;s
          board and it runs like the real thing: a brief, a prep timer, then your
          presentation, then the judge.
        </li>
        <li>
          <strong>You only see what a competitor would see, when they&rsquo;d see
          it.</strong>{" "}
          The brief gives you the performance indicators and the
          participant instructions. The situation and its exhibit open when your
          prep time starts. The judge&rsquo;s character and their questions stay
          hidden until you start presenting — and the questions arrive{" "}
          <strong>one at a time</strong>, so you have to answer each one before
          you find out what the next one is.
        </li>
        <li>
          The clock matches your event&rsquo;s real timings — 10 minutes to prep and
          10 to present for individual and Principles events, 30 and 15 for Team
          Decision Making. It&rsquo;s there to practise against, not to police you:
          pause it, reset it, or skip ahead whenever you like.
        </li>
        <li>
          At the end you score yourself on each performance indicator against the
          same four levels a DECA judge uses, and the whole scenario unlocks so you
          can re-read it knowing what you were being asked.
        </li>
        <li>
          <strong>Nothing from a roleplay is saved yet.</strong>{" "}
          Your self-scores
          stay on the screen and clear when you close the run, and running a
          roleplay doesn&rsquo;t move your progress or readiness — making it stick
          is the next piece we&rsquo;re building.
        </li>
      </Entry>

      <Entry date="July 2026" title="Roleplays: a new challenge every day">
        <li>
          <strong>The roleplay generator is gone</strong>, and the Roleplays page
          is now a <strong>daily challenge</strong> instead. Rather than asking
          for one scenario at a time, each day gets its own fresh set of
          role-play case studies across the 28 competitive events, and every day
          stays in a permanent archive you can go back through.
        </li>
        <li>
          New scenarios drop at <strong>midnight Eastern</strong>, and that&rsquo;s
          the same moment for everyone — so if you&rsquo;re in California the next
          day opens up at 9pm your time, and you and a teammate three time zones
          away are always practising the same set.
        </li>
        <li>
          Each scenario comes with its performance indicators, participant
          instructions, the situation, the judge&rsquo;s characterization and the
          judge&rsquo;s questions — and they&rsquo;re written to be harder than the
          district-level material DECA publishes.
        </li>
        <li>
          <strong>This one is genuinely early.</strong>{" "}
          There are only a few days
          in the archive so far, and on each of them most events aren&rsquo;t
          filled in yet — those show up greyed out as &ldquo;not available for
          this day&rdquo; rather than being quietly hidden, so you can always see
          what&rsquo;s there and what isn&rsquo;t.
        </li>
        <li>
          You can browse the day&rsquo;s line-up and the whole archive — and, as of
          the update above, open a scenario and actually run it.
        </li>
      </Entry>

      <Entry date="July 2026" title="A much deeper finance question bank">
        <li>
          The finance bank nearly tripled — from about 1,270 questions to
          over <strong>3,500</strong> — with District, Association and ICDC each
          gaining hundreds of new questions.
        </li>
        <li>
          The point wasn&rsquo;t just more questions. Every finance performance
          indicator now has enough questions behind it to actually review with:
          before, plenty of PIs had one or two questions total, so a{" "}
          <strong>Practice this PI</strong> drill from your mastery heatmap ran
          out almost immediately, or handed you the same question twice.
        </li>
        <li>
          Each PI is also filled at every difficulty, so a drill can start you
          easy and work up instead of throwing whatever it happens to have at
          you. Questions written to be hard are checked by two independent
          reviewers, and anything that turns out to be a medium question in
          disguise gets relabelled — a &ldquo;hard&rdquo; badge should mean
          something.
        </li>
        <li>
          Marketing, business management, entrepreneurship and hospitality are
          unchanged for now. Finance went first; the others follow. (Business
          Administration Core has since been done too — see the newer entry
          above.)
        </li>
      </Entry>

      <Entry date="July 2026" title="Practice tests and vocab now ask you to sign in">
        <li>
          Practice Tests, Vocab Terms and Roleplays are account features, but if
          you had a direct link to one — a bookmark, a link a friend sent you,
          something in your history — it opened without an account. Anything you
          answered there was quietly thrown away, because scores only save to an
          account.
        </li>
        <li>
          Those links now show a short sign-up card instead, so nothing you
          practice goes unrecorded. The <strong>Question Bank</strong> is still
          free to browse without an account, and making one takes a username and
          a password — no email.
        </li>
      </Entry>

      <Entry date="July 2026" title="No more repeated questions inside one test">
        <li>
          Ten Finance · District questions had accidentally been written twice —
          word-for-word the same question, with the answer choices reworded — so a
          single practice test could ask you the same thing twice, sometimes
          labelled <strong>Easy</strong> one time and <strong>Medium</strong> the
          next. The repeats are gone, and new questions are now checked against
          every question already in the bank before they can join it.
        </li>
        <li>
          If one of those repeats happens to be sitting in your Error Log, it
          simply drops off the list. Your scores and progress are untouched.
        </li>
      </Entry>

      <Entry date="July 2026" title="Your study plan survives a late-night session">
        <li>
          If you left your dashboard open past midnight, the plan could lose the
          day&rsquo;s work the moment you pressed <strong>Start</strong>{" "}
          — tasks you&rsquo;d added disappeared, ones you&rsquo;d removed came back, and
          the task you just started sat at 0 no matter how many questions you
          answered, until you reloaded.
        </li>
        <li>
          The dashboard now notices the day change on its own and rolls over to a
          fresh plan — no reload, and nothing lost on the way there.
        </li>
      </Entry>

      <Entry date="July 2026" title="Easier to read your question map at a glance">
        <li>
          In the <strong>Jump to</strong> panel beside a focus quiz or generated
          test, the squares for questions you got <strong>right</strong> and
          questions you <strong>skipped</strong> were nearly the same colour on
          some themes — worst of all on First Bloom, where they were effectively
          identical. Each result now has its own colour, tuned per theme.
        </li>
        <li>
          Skipped questions also get a dashed outline of their own, so they no
          longer look the same as questions you&rsquo;ve merely looked at and
          haven&rsquo;t answered yet. The little legend underneath now lists{" "}
          <strong>seen</strong> alongside correct, wrong and skip.
        </li>
      </Entry>

      <Entry date="July 2026" title="Practice keeps saving after a storage hiccup">
        <li>
          If your browser briefly refused to save — low disk space, private
          browsing, or storage being cleared in another tab — DECK could stop
          recording your practice for the rest of the visit, leaving your
          dashboard looking empty until you reloaded the page. It now recovers on
          its own the moment the problem clears.
        </li>
        <li>
          If your device ever does stop saving, DECK now tells you instead of
          quietly carrying on — so an empty Progress page always means &ldquo;you
          haven&rsquo;t practised yet&rdquo;, never &ldquo;we lost it&rdquo;.
        </li>
        <li>
          <strong>Reset progress</strong> and <strong>Export my data</strong>{" "}
          in
          Settings now report it when they don&rsquo;t work, rather than showing a
          tick for a reset that didn&rsquo;t happen.
        </li>
      </Entry>

      <Entry date="July 2026" title="Move through questions faster">
        <li>
          In focus quizzes and generated tests, you can now press{" "}
          <strong>Enter</strong> to jump to the next question (or finish on the
          last one) — no more reaching for the mouse between questions. Picking an
          answer with the keyboard still works exactly as before.
        </li>
        <li>
          The <strong>Skip question</strong> link now simply moves you on to the
          next question instead of marking it skipped and revealing the answer — so
          you can breeze past a question without spoiling it.
        </li>
      </Entry>

      <Entry date="July 2026" title="Sync catches up on power users">
        <li>
          Fixed a bug where signing in on a new device could miss some of your
          practice history. Now all your answers sync across devices, even if
          you&rsquo;ve worked through thousands of questions.
        </li>
      </Entry>

      <Entry date="July 2026" title="More reliable progress syncing">
        <li>
          Your progress now keeps syncing across your devices even if one item
          hits a snag on the way to the server — a single problem update no longer
          quietly stops everything after it from syncing.
        </li>
        <li>
          If something genuinely can&rsquo;t be synced, you&rsquo;ll now see a
          brief heads-up. Either way your practice is always saved on the device
          you&rsquo;re using.
        </li>
      </Entry>

      <Entry date="July 2026" title="One device at a time">
        <li>
          For your security, an account can now be signed in on only one device at
          a time. Logging in somewhere new automatically signs out the older
          session — if that happens to you, just sign back in.
        </li>
      </Entry>

      <Entry date="July 2026" title="Study plan tasks fixed up">
        <li>
          Fixed a bug where practice on some accounts wasn&rsquo;t counting —
          your task progress bar and readiness now update reliably as you answer.
        </li>
        <li>
          Each task now <strong>saves your progress</strong>: leave a task
          part-way and come back later and you&rsquo;ll resume the same questions
          right where you left off.
        </li>
        <li>
          Your daily <strong>Today&rsquo;s plan</strong> is now set once at the
          start of the day and stays put — no more surprise extra tasks appearing
          while you study. You can still add your own tasks anytime.
        </li>
        <li>
          Tasks for a performance indicator no longer ask for more questions than
          the bank actually has, so a short drill can be finished.
        </li>
        <li>
          <strong>Learn</strong>{" "}
          tasks are now a quick 3 questions and pull ones you
          haven&rsquo;t seen yet — so you&rsquo;re always learning something new (and
          you&rsquo;ll get fewer if that&rsquo;s all that&rsquo;s left).
        </li>
      </Entry>

      <Entry date="July 2026" title="Developers page is live">
        <li>
          The <strong>Developers</strong> page is now unlocked — a quick look at
          the DECA alumni and volunteers building DECK.
        </li>
      </Entry>

      <Entry date="July 2026" title="Accounts & cross-device sync (beta)">
        <li>
          Optional <strong>username + password accounts</strong> — no email
          needed. Guest mode is still the default and needs no account.
        </li>
        <li>
          Your practice now <strong>syncs across devices</strong>{" "}
          when
          you&rsquo;re signed in, and keeps working offline (it catches up when
          you&rsquo;re back online).
        </li>
        <li>
          New <strong>Settings → Data</strong> controls: export your data, reset
          your progress, or delete your account.
        </li>
        <li>
          Guest mode now <strong>records nothing</strong> — progress tracking is
          account-only. See the{" "}
          <Link href="/privacy" className="underline hover:text-ink">
            privacy page
          </Link>{" "}
          for the details.
        </li>
      </Entry>

      <Entry date="July 2026" title="Themes tune-up">
        <li>
          New <strong>Animated effects</strong> toggle in Settings → Themes — turn
          the seasonal petals, seeds, and snow on or off.
        </li>
        <li>Retired the Blueprint theme; six themes remain, three of them seasonal.</li>
      </Entry>

      <Entry date="July 2026" title="Bigger banks">
        <li>
          <strong>Vocab</strong> expanded to 50 terms per event (1,400 total
          across every cluster).
        </li>
        <li>
          The <strong>question bank</strong>{" "}
          roughly doubled to ~6,166 questions, with deeper &ldquo;hard&rdquo;
          shelves across all five clusters.
        </li>
      </Entry>

      <Entry date="June 2026" title="Test Generator on the real bank">
        <li>
          The Test Generator now composes difficulty-mixed{" "}
          <strong>25 / 50-question tests</strong> from the real committed bank —
          instantly, with no model compute.
        </li>
        <li>
          Mix presets — <strong>Exam-real</strong>, <strong>Balanced</strong>, and{" "}
          <strong>Challenge</strong> — plus one-tap Regenerate.
        </li>
      </Entry>

      <Entry date="June 2026" title="Progress & Review">
        <li>
          <strong>Progress</strong> — a mastery dashboard with a readiness
          trajectory and a per-PI heatmap you can drill into.
        </li>
        <li>
          <strong>Review</strong> — an error log of everything you missed, grouped
          by topic; questions drop off once you get them right again.
        </li>
      </Entry>

      <Entry date="Spring 2026" title="Question Bank + focus mode">
        <li>
          A browsable, difficulty-tagged <strong>question bank</strong> with an
          Easy / Medium / Hard badge on every question.
        </li>
        <li>
          A no-typing <strong>focus quiz</strong> mode with a side-by-side 100-Q
          navigator.
        </li>
      </Entry>

      <p className="mt-10 text-sm text-muted">
        Spotted a bug or have a suggestion? See{" "}
        <Link href="/help" className="underline hover:text-ink">
          Help
        </Link>{" "}
        for how to reach us.
      </p>
    </div>
  );
}
