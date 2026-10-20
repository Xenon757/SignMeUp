import { useRef, useState } from 'react';
import { ACCEPTED, extensionOf } from '../api';

interface Props {
  onFile: (file: File) => void;
}

/** Drop a video or audio file, or pick one. */
export function Upload({ onFile }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const take = (file: File | undefined) => {
    if (!file) return;
    if (!ACCEPTED.includes(extensionOf(file.name))) {
      setProblem(`${file.name} isn't a supported file. Use a video (MP4, MOV, WebM, MKV) or audio (MP3, WAV, M4A).`);
      return;
    }
    setProblem(null);
    onFile(file);
  };

  return (
    <div className="upload">
      <label
        className={`dropzone${dragging ? ' dragging' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); take(e.dataTransfer.files[0]); }}
      >
        <input
          ref={input}
          type="file"
          accept={['video/*', 'audio/*', ...ACCEPTED].join(',')}
          onChange={e => take(e.target.files?.[0])}
        />
        <span className="dropzone-icon" aria-hidden="true">⬆</span>
        <span className="dropzone-title">Drop a video or audio file</span>
        <span className="dropzone-hint">or <u>choose a file</u></span>
      </label>
      {problem && <p className="problem" role="alert">{problem}</p>}
    </div>
  );
}
