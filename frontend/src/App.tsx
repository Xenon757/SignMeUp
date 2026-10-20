import { ComparePage } from './pages/ComparePage';
import { HomePage } from './pages/HomePage';

const REPO = 'https://github.com/Xenon757/SignMeUp';

/** Two pages, picked by URL; Flask serves this app for both. */
export default function App() {
  const comparing = window.location.pathname.startsWith('/compare');
  return (
    <div className="app">
      <header className="site-header">
        <a className="brand" href="/">
          <img src="/static/img/logo.png" alt="" width={36} height={36} />
          <span>SignMeUp</span>
        </a>
        <nav>
          <a href="/compare" aria-current={comparing ? 'page' : undefined}>Compare signs</a>
          <a href={REPO} target="_blank" rel="noopener">GitHub</a>
        </nav>
      </header>

      {comparing ? <ComparePage /> : <HomePage />}

      <footer className="site-footer">
        <p>
          Sign videos from <a href="https://aslsignbank.com" target="_blank" rel="noopener">ASL Signbank</a> (Hochgesang,
          Crasborn &amp; Lillo-Martin, CC BY-NC-SA 4.0), animated with MediaPipe. Fingerspelling images from Wikimedia
          Commons (public domain). Speech recognition by Whisper.
        </p>
        <p>
          Originally built at Hello World 2025 by the SignMeUp team (<a href="https://github.com/ShlokShar/SignMeUp" target="_blank" rel="noopener">original repo</a>).
        </p>
      </footer>
    </div>
  );
}
