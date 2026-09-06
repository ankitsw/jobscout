import { formatDate } from '../lib/format.js';

export default function ResumeManager({ resumes, onUpload, onDelete, onClose }) {
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
            onUpload(fileInput.files[0]);
            fileInput.value = '';
          }}
        >
          <input type="file" name="resumeFile" accept="application/pdf" />
          <button className="action-button" type="submit">Upload PDF</button>
        </form>

        <div className="resume-list">
          {resumes.length === 0 ? (
            <div className="muted">No resumes uploaded yet.</div>
          ) : (
            resumes.map((resume) => (
              <div className="resume-list-item" key={resume.id}>
                <div>
                  <div className="resume-list-title">Resume #{resume.id}</div>
                  <div className="muted resume-list-preview">
                    {(resume.content || '').replace(/\s+/g, ' ').trim().slice(0, 140) || 'No text extracted'}
                  </div>
                  <div className="muted resume-list-date">Uploaded {formatDate(resume.created_at)}</div>
                </div>
                <button
                  className="ghost-button small"
                  onClick={() => {
                    if (confirm(`Delete resume #${resume.id}? This cannot be undone.`)) onDelete(resume.id);
                  }}
                >
                  Delete
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
