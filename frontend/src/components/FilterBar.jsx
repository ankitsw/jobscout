export default function FilterBar({ filters, onChange }) {
  const set = (key) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    onChange({ ...filters, [key]: value });
  };

  return (
    <div className="filter-bar">
      <div className="filter-row">
        <label className="filter-field">
          <span className="tiny-label">Sort by</span>
          <select value={filters.sortBy} onChange={set('sortBy')}>
            <option value="score">Best match</option>
            <option value="newest">Date posted (newest)</option>
            <option value="company">Company (A-Z)</option>
          </select>
        </label>
        <label className="filter-field">
          <span className="tiny-label">Platform</span>
          <select value={filters.platform} onChange={set('platform')}>
            <option value="">All platforms</option>
            <option value="linkedin">LinkedIn</option>
            <option value="ats_greenhouse">Greenhouse</option>
            <option value="ats_lever">Lever</option>
          </select>
        </label>
      </div>
      <div className="filter-row">
        <label className="filter-field">
          <span className="tiny-label">Job type</span>
          <select value={filters.jobType} onChange={set('jobType')}>
            <option value="">Any type</option>
            <option value="full_time">Full-time</option>
            <option value="part_time">Part-time</option>
            <option value="contract">Contract</option>
            <option value="internship">Internship</option>
          </select>
        </label>
        <label className="filter-field">
          <span className="tiny-label">Experience</span>
          <select value={filters.experienceLevel} onChange={set('experienceLevel')}>
            <option value="">Any level</option>
            <option value="entry">Entry (0-2 yrs)</option>
            <option value="mid">Mid (2-5 yrs)</option>
            <option value="senior">Senior (5-8 yrs)</option>
            <option value="lead">Lead+ (8+ yrs)</option>
          </select>
        </label>
      </div>
      <label className="filter-checkbox">
        <input type="checkbox" checked={filters.remoteOnly} onChange={set('remoteOnly')} />
        <span>Remote only</span>
      </label>
    </div>
  );
}
