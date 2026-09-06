import { Link } from 'react-router-dom';
import JobCard from './JobCard.jsx';
import FilterBar from './FilterBar.jsx';

export default function JobsPanel({
  visibleJobs,
  selectedJobId,
  onSelectJob,
  search,
  onSearchChange,
  filters,
  onFiltersChange,
  filterBarOpen,
  onToggleFilterBar,
}) {
  return (
    <aside className="panel jobs-panel">
      <div className="panel-header">
        <div className="panel-title">Jobs</div>
        <div className="panel-header-actions">
          <button className="ghost-button small" onClick={onToggleFilterBar}>Filter</button>
          <span className="status-pill"><span className="dot" /> Live</span>
        </div>
      </div>

      <input
        className="search-box"
        type="text"
        placeholder="Search jobs, skills, companies..."
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
      />

      {filterBarOpen && <FilterBar filters={filters} onChange={onFiltersChange} />}

      <div className="job-list">
        {visibleJobs.length === 0 ? (
          <div className="job-card"><div className="muted">No jobs match the current filters.</div></div>
        ) : (
          visibleJobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              isActive={String(job.id) === String(selectedJobId)}
              onSelect={onSelectJob}
            />
          ))
        )}
      </div>

      <Link to="/jobs-all" className="show-all-link">View as table &rarr;</Link>
    </aside>
  );
}
