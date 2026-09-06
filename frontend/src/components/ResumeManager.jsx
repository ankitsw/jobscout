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

export default function ResumeManager({ resumes, onUpload, onDelete, onRename, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h2>Resumes</h2>
          <button className="ghost-button small" onClick={onClose}>Close</button>
        </div>

        <form
          className="resume-upload-form"
          encType="multipart/form-data"
          onSubmit={(event) => {
            event.preventDefault();
            const fileInput = event.target.elements.resumeFile;
            const nameInput = event.target.elements.resumeName;
            onUpload(fileInput.files[0], nameInput.value.trim());
            fileInput.value = '';
            nameInput.value = '';
          }}
        >
          <input type="text" name="resumeName" placeholder="Name (optional)" className="resume-name-input" />
          <input type="file" name="resumeFile" accept="application/pdf" />
          <button className="action-button" type="submit">Upload PDF</button>
        </form>

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
