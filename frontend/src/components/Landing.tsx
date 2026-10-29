import { EXTENSION } from '../links';
import { SignPreview } from './SignPreview';
import { Upload } from './Upload';

const SOURCES = {
  nidcd: 'https://www.nidcd.nih.gov/health/american-sign-language',
  traxler: 'https://doi.org/10.1093/deafed/5.4.337',
  marschark: 'https://www.handsandvoices.org/articles/research/v9-2_marschark.htm',
  debevc: 'https://doi.org/10.1371/journal.pone.0127577',
};

/** The landing page: upload, how it works, and why ASL matters (with sources). */
export function Landing({ onFile }: { onFile: (file: File) => void }) {
  return (
    <div className="landing">
      <section className="hero">
        <div className="hero-text">
          <p className="eyebrow">ASL for any video</p>
          <h1>Stories should be understood by all</h1>
          <p className="lede">
            Upload a video or audio clip. SignMeUp transcribes the speech, translates it into ASL, and signs it with an
            animated signer, in time with the speech and right inside the video.
          </p>
          <Upload onFile={onFile} />
          <p className="muted small">Video (MP4, MOV, WebM) or audio (MP3, WAV, M4A), up to 200 MB. Nothing is kept after processing.</p>
          <a className="demo-link" href="/demo">No video handy? Watch the demo: the first YouTube video, signed <span aria-hidden="true">→</span></a>
          <div className="extension-cta">
            <div>
              <p className="extension-title">Watching on YouTube?</p>
              <p className="muted small">The free Chrome extension signs YouTube videos as you watch, from their captions.</p>
            </div>
            <a className="button-link" href={EXTENSION} target="_blank" rel="noopener">Add to Chrome</a>
          </div>
        </div>
        <div className="hero-art">
          <SignPreview />
        </div>
      </section>

      <section className="band" aria-labelledby="how">
        <p className="eyebrow">How it works</p>
        <h2 id="how">From speech to signing in three steps</h2>
        <ol className="steps">
          <li>
            <span className="step-number">1</span>
            <h3>Listen</h3>
            <p>Whisper transcribes the speech and notes when every word is said.</p>
          </li>
          <li>
            <span className="step-number">2</span>
            <h3>Translate</h3>
            <p>Each sentence is turned into ASL: grammar words like “the” and “is” are dropped, signs use base forms, negation is always signed, and question words move to the end.</p>
          </li>
          <li>
            <span className="step-number">3</span>
            <h3>Sign</h3>
            <p>Each sign is animated from a real signer’s video on ASL Signbank and timed to the speech. Words with no sign are fingerspelled.</p>
          </li>
        </ol>
      </section>

      <section className="band mission" aria-labelledby="why">
        <p className="eyebrow">Our mission</p>
        <h2 id="why">Why ASL, and not just captions?</h2>
        <p className="mission-lede">
          Captions are written English. But for many Deaf people, ASL is their first language and English is their second,
          so captions alone can mean watching in a second language. SignMeUp signs the speech in ASL <em>and</em> keeps
          the captions, with the word being signed highlighted.
        </p>
        <div className="facts">
          <article className="fact">
            <p className="fact-big">Its own language</p>
            <p>
              ASL is “a complete, natural language” whose grammar “differs from English”, and the primary language of many
              Deaf and hard of hearing North Americans.
            </p>
            <p className="source">National Institute on Deafness and Other Communication Disorders · <a href={SOURCES.nidcd} target="_blank" rel="noopener">source</a></p>
          </article>
          <article className="fact">
            <p className="fact-big">~4th grade</p>
            <p>
              The median English reading comprehension of deaf and hard of hearing high school graduates in a national
              study. Half read above that level, and researchers caution that the figure is often over-simplified.
            </p>
            <p className="source">
              Traxler (2000), <i>J. Deaf Studies &amp; Deaf Education</i> · <a href={SOURCES.traxler} target="_blank" rel="noopener">study</a> ·{' '}
              <a href={SOURCES.marschark} target="_blank" rel="noopener">context</a>
            </p>
          </article>
          <article className="fact">
            <p className="fact-big">+24%</p>
            <p>
              Deaf viewers understood signed videos 24% better when captions were added to the signing, in a study of 51
              sign language users. Signing and captions together beat either alone.
            </p>
            <p className="source">Debevc et al. (2015), <i>PLoS ONE</i> · <a href={SOURCES.debevc} target="_blank" rel="noopener">study</a></p>
          </article>
        </div>
        <p className="muted small honest">
          SignMeUp is a student project: it strings together dictionary signs and can’t match a fluent human interpreter,
          who adds facial grammar, space and expression. It’s a step toward making more video accessible, not a replacement.
        </p>
      </section>
    </div>
  );
}
