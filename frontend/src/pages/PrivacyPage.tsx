import { REPO } from '../links';

/** What the website and the browser extension do with data. Keep in step with the code. */
export function PrivacyPage() {
  return (
    <main className="prose">
      <h1>Privacy policy</h1>
      <p className="muted">Last updated October 25, 2026. Covers the SignMeUp website and the SignMeUp browser extension.</p>

      <p>
        SignMeUp is a free, non-commercial project. It has no accounts, no ads and no analytics, and it doesn't sell or
        share data.
      </p>

      <h2>The browser extension</h2>
      <ul>
        <li>
          <strong>What it reads:</strong> on YouTube watch pages, the English captions of the video you're watching (the
          caption text and when each line is said). It does not read your YouTube account, history, comments or anything
          else on the page.
        </li>
        <li>
          <strong>What it sends:</strong> those caption lines, a minute at a time, to SignMeUp's server
          (signmeup.fly.dev), which sends back the signs to show. It doesn't send which video it is, who you are, or any
          other information.
        </li>
        <li>
          <strong>What the server keeps:</strong> the signed result for each chunk of captions, filed under a code made
          from the caption text itself, so the same captions are only translated once. It isn't linked to you or to a
          video.
        </li>
        <li>
          <strong>What stays in your browser:</strong> whether signing is turned on, saved with Chrome's own extension
          storage (which Chrome may sync across your signed-in devices).
        </li>
      </ul>

      <h2>The website</h2>
      <ul>
        <li>
          <strong>Uploads:</strong> a video or audio file you upload is saved under a random name, transcribed and signed,
          and deleted as soon as that's done. The result (the transcript and signs) is kept in the server's memory for up
          to an hour so the page can show it, then discarded.
        </li>
        <li>
          <strong>Your settings:</strong> where the signer box goes and its size are saved in your browser's local
          storage, not on the server.
        </li>
        <li>
          <strong>Other services the pages load:</strong> fonts from Google Fonts, and on the demo page, YouTube's
          embedded player (from youtube-nocookie.com). Those services receive your browser's usual request information
          under their own privacy policies.
        </li>
      </ul>

      <h2>Hosting</h2>
      <p>
        The server runs on Fly.io, which handles the network requests to it. SignMeUp's own code doesn't record IP
        addresses or keep request logs.
      </p>

      <h2>Contact</h2>
      <p>
        Questions or requests: open an issue at <a href={`${REPO}/issues`} target="_blank" rel="noopener">{REPO}/issues</a>.
      </p>
    </main>
  );
}
