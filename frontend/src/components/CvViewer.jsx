import { useState } from 'react';

export default function CvViewer({ job, cv, onClose }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(cv);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API unavailable; nothing to fall back to gracefully
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card cv-viewer" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>Tailored CV</h2>
            {job && <div className="muted">{job.title} · {job.company}</div>}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="ghost-button small" onClick={handleCopy}>{copied ? 'Copied' : 'Copy'}</button>
            <button className="ghost-button small" onClick={onClose}>Close</button>
          </div>
        </div>
        <pre className="cv-content">{cv}</pre>
      </div>
    </div>
  );
}
