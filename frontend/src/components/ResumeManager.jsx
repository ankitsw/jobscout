import { useState } from 'react';
import { formatDate } from '../lib/format.js';

function ResumeRow({ resume, onDelete, onRename }) {
  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState(resume.name || '');

  function save() {
    const trimmed = draftName.trim();
    setEditing(false);
    if (trimmed && trimmed !== resume.name) onRename(resume.id, trimmed);
    else setDraftName(resume.name || '');
  }

  return (
    <div className="resume-list-item">
      <div>
        {editing ? (
          <input
            className="resume-rename-input"
            autoFocus
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            onBlur={save}
            onKeyDown={(event) => {
              if (event.key === 'Enter') save();
              if (event.key === 'Escape') {
                setDraftName(resume.name || '');
                setEditing(false);
              }
            }}
          />
        ) : (
          <div className="resume-list-title">
            {resume.name || `Resume #${resume.id}`}
            <button className="rename-link" onClick={() => setEditing(true)}>Rename</button>
          </div>
        )}
        <div className="muted resume-list-preview">
          {(resume.content || '').replace(/\s+/g, ' ').trim().slice(0, 140) || 'No text extracted'}
        </div>
        <div className="muted resume-list-date">Uploaded {formatDate(resume.created_at)}</div>
      </div>
      <button
        className="ghost-button small"
        onClick={() => {
          if (confirm(`Delete "${resume.name || `Resume #${resume.id}`}"? This cannot be undone.`)) onDelete(resume.id);
        }}
      >
        Delete
      </button>
    </div>
  );
}

function UploadForm({ onUpload }) {
  const [file, setFile] = useState(null);
  const [name, setName] = useState('');
  const [dragOver, setDragOver] = useState(false);

  function pickFile(candidate) {
    if (candidate && candidate.type === 'application/pdf') setFile(candidate);
    else if (candidate) alert('Please choose a PDF file.');
  }

  function submit(event) {
    event.preventDefault();
    if (!file) {
      alert('Choose or drop a PDF file first.');
      return;
    }
    onUpload(file, name.trim());
    setFile(null);
    setName('');
  }

  return (
    <form className="resume-upload-form" onSubmit={submit}>
      <input
        type="text"
        placeholder="Name (optional)"
        className="resume-name-input"
        value={name}
        onChange={(event) => setName(event.target.value)}
      />

      <label
        className={`resume-dropzone${dragOver ? ' drag-over' : ''}`}
        onDragOver={(event) => { event.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          pickFile(event.dataTransfer.files?.[0]);
        }}
      >
        <input
          type="file"
          accept="application/pdf"
          hidden
          onChange={(event) => pickFile(event.target.files?.[0])}
        />
        {file ? file.name : 'Drop a PDF here, or click to browse'}
      </label>

      <button className="action-button" type="submit" disabled={!file}>Upload PDF</button>
    </form>
  );
}

export default function ResumeManager({ resumes, onUpload, onDelete, onRename, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h2>Resumes</h2>
          <button className="ghost-button small" onClick={onClose}>Close</button>
        </div>

        <UploadForm onUpload={onUpload} />

        <div className="resume-list">
          {resumes.length === 0 ? (
            <div className="muted">No resumes uploaded yet.</div>
          ) : (
            resumes.map((resume) => (
              <ResumeRow key={resume.id} resume={resume} onDelete={onDelete} onRename={onRename} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
