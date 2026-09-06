import { scoreFor, formatDate } from '../lib/format.js';

export default function JobCard({ job, isActive, onSelect }) {
  return (
    <div
      className={`job-card${isActive ? ' active' : ''}`}
      onClick={() => onSelect(job.id)}
    >
      <div className="job-topline">
        <div>
          <div className="company">{job.company || 'Company'}</div>
          <div className="job-title">{job.title || 'Untitled role'}</div>
        </div>
        <div className="score">{scoreFor(job)}%</div>
      </div>
      <div className="meta-row">
        <span className="chip">{job.location || 'Remote'}</span>
        <span className="chip">{job.platform || 'Platform'}</span>
        <span className="chip">{formatDate(job.posted_at)}</span>
      </div>
    </div>
  );
}
