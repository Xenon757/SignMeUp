import { ComparePage } from './pages/ComparePage';
import { DemoPage } from './pages/DemoPage';
import { HomePage } from './pages/HomePage';
import { PrivacyPage } from './pages/PrivacyPage';

const REPO = 'https://github.com/Xenon757/SignMeUp';

/** Pages, picked by URL; Flask serves this app for each. */
export default function App() {
  const path = window.location.pathname;
  const comparing = path.startsWith('/compare');
  const demo = path.startsWith('/demo');
  const privacy = path.startsWith('/privacy');
  return (
    <div className="app">
      <header className="site-header">
        <a className="brand" href="/">
          <img src="/static/img/logo.png" alt="" width={36} height={36} />
          <span>SignMeUp</span>
        </a>
        <nav>
          <a href="/demo" aria-current={demo ? 'page' : undefined}>Demo</a>
          <a href="/compare" aria-current={comparing ? 'page' : undefined}>Compare signs</a>
          <a href={REPO} target="_blank" rel="noopener">GitHub</a>
        </nav>
      </header>

      {comparing ? <ComparePage /> : demo ? <DemoPage /> : privacy ? <PrivacyPage /> : <HomePage />}

      <footer className="site-footer">
        <p>
          Sign videos from <a href="https://aslsignbank.com" target="_blank" rel="noopener">ASL Signbank</a> (Hochgesang,
          Crasborn &amp; Lillo-Martin, CC BY-NC-SA 4.0), animated with MediaPipe. Fingerspelling images from Wikimedia
          Commons (public domain). Speech recognition by Whisper.
        </p>
        <p>
          Originally built at Hello World 2025 by the SignMeUp team (<a href="https://github.com/ShlokShar/SignMeUp" target="_blank" rel="noopener">original repo</a>).
          {' '}<a href="/privacy">Privacy policy</a>
        </p>
      </footer>
    </div>
  );
}
