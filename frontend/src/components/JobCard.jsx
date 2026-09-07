import { matchScoreFor, formatDate } from '../lib/format.js';

export default function JobCard({ job, isActive, onSelect, matchScores }) {
  const score = matchScoreFor(job, matchScores);
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
        <div className={`score${score == null ? ' score-empty' : ''}`} title={score == null ? 'Select a resume to see match score' : undefined}>
          {score == null ? '—' : `${score}%`}
        </div>
      </div>
      <div className="meta-row">
        <span className="chip">{job.location || 'Remote'}</span>
        <span className="chip">{job.platform || 'Platform'}</span>
        <span className="chip">{formatDate(job.posted_at)}</span>
      </div>
    </div>
  );
}
