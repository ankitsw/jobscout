import { scoreFor, formatLakhs } from '../lib/format.js';

export default function DetailPanel({
  job,
  detailExtras,
  resumes,
  selectedResumeId,
  onSelectResume,
  onUploadResume,
  onGenerateCv,
}) {
  if (!job) {
    return (
      <section className="panel detail-panel">
        <div className="detail-header">
          <div>
            <div className="muted">Select a job</div>
            <h2>No job selected</h2>
          </div>
          <div className="score">--</div>
        </div>
      </section>
    );
  }

  const { classification, rating, reviewsCount, salary, description } = detailExtras;
  const showMeta = Boolean(classification) || rating != null;

  return (
    <section className="panel detail-panel">
      <div className="detail-header">
        <div>
          <div className="muted">{job.company || 'Company'}</div>
          <h2>{job.title || 'Untitled role'}</h2>
          {showMeta && (
            <div className="company-meta">
              {classification && <span className="chip">{classification}</span>}
              {rating != null && (
                <span className="rating-chip">
                  &#9733; {rating.toFixed(1)}{reviewsCount ? ` (${reviewsCount.toLocaleString()} reviews)` : ''}
                </span>
              )}
            </div>
          )}
        </div>
        <div className="score">{scoreFor(job)}%</div>
      </div>

      <div className="detail-actions">
        <button className="action-button" onClick={onGenerateCv}>Generate CV for this job</button>
        {job.url && (
          <a className="ghost-button" href={job.url} target="_blank" rel="noopener noreferrer">
            Open posting &#8599;
          </a>
        )}
      </div>

      <div className="subtle-card">
        <div className="tiny-label">Overview</div>
        <div className="mini-grid">
          <div className="mini-tile">
            <div className="tiny-label">Location</div>
            <div>{job.location || 'Remote'}</div>
          </div>
          <div className="mini-tile">
            <div className="tiny-label">Experience</div>
            <div>{job.experience_required || 'Not specified'}</div>
          </div>
          <div className="mini-tile">
            <div className="tiny-label">Platform</div>
            <div>{job.platform || 'Platform'}</div>
          </div>
          <div className="mini-tile">
            <div className="tiny-label">Est. Salary</div>
            <div
              title={salary ? `Based on AmbitionBox's "${salary.matched_title}" band at ${job.company} (${salary.data_points} data points)` : undefined}
            >
              {salary ? `${formatLakhs(salary.typical_min_ctc)} – ${formatLakhs(salary.typical_max_ctc)}` : '—'}
            </div>
          </div>
        </div>
      </div>

      <div className="subtle-card">
        <div className="tiny-label">Role description</div>
        <div className="job-desc">{description}</div>
      </div>

      <div className="subtle-card resume-box">
        <div className="tiny-label">Resume</div>
        <select value={selectedResumeId ?? ''} onChange={(event) => onSelectResume(event.target.value ? Number(event.target.value) : null)}>
          <option value="">Select a resume</option>
          {resumes.map((resume) => (
            <option key={resume.id} value={resume.id}>Resume #{resume.id}</option>
          ))}
        </select>

        <form
          encType="multipart/form-data"
          onSubmit={(event) => {
            event.preventDefault();
            const fileInput = event.target.elements.resumeFile;
            onUploadResume(fileInput.files[0]);
            fileInput.value = '';
          }}
        >
          <input type="file" name="resumeFile" accept="application/pdf" />
          <div style={{ marginTop: 10, display: 'flex', gap: 10 }}>
            <button className="action-button" type="submit">Upload PDF</button>
          </div>
        </form>
      </div>
    </section>
  );
}
