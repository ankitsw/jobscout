import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import CompanyTooltip from '../components/CompanyTooltip.jsx';
import { api } from '../lib/api.js';
import { scoreFor, formatDate, platformLabel, platformClass } from '../lib/format.js';

const HOVER_DELAY_MS = 250;

export default function JobsTablePage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [search, setSearch] = useState('');
  const [tooltip, setTooltip] = useState(null); // { name, position, profile }

  const profileCache = useRef(new Map());
  const hoverTimer = useRef(null);
  const activeCompany = useRef(null);

  useEffect(() => {
    api.listJobs()
      .then((data) => setJobs(Array.isArray(data) ? data : []))
      .catch(() => setJobs([]));
  }, []);

  useEffect(() => {
    function hide() {
      clearTimeout(hoverTimer.current);
      activeCompany.current = null;
      setTooltip(null);
    }
    window.addEventListener('scroll', hide, true);
    return () => window.removeEventListener('scroll', hide, true);
  }, []);

  const rows = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return jobs;
    return jobs.filter((job) => {
      const haystack = `${job.title} ${job.company} ${job.location} ${job.description}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [jobs, search]);

  function positionFor(rect) {
    const tooltipWidth = 300;
    let left = rect.left;
    if (left + tooltipWidth > window.innerWidth - 16) {
      left = window.innerWidth - tooltipWidth - 16;
    }
    return { left: Math.max(16, left), top: rect.bottom + 8 };
  }

  async function showTooltip(name, rect) {
    activeCompany.current = name;
    const position = positionFor(rect);

    if (profileCache.current.has(name)) {
      setTooltip({ name, position, profile: profileCache.current.get(name) });
      return;
    }

    setTooltip({ name, position, profile: undefined });
    try {
      const profile = await api.companyResearch(name);
      profileCache.current.set(name, profile);
      if (activeCompany.current === name) {
        setTooltip({ name, position, profile });
      }
    } catch {
      if (activeCompany.current === name) {
        setTooltip({ name, position, profile: null });
      }
    }
  }

  function handleMouseEnter(name, event) {
    const rect = event.currentTarget.getBoundingClientRect();
    clearTimeout(hoverTimer.current);
    hoverTimer.current = setTimeout(() => showTooltip(name, rect), HOVER_DELAY_MS);
  }

  function handleMouseLeave() {
    clearTimeout(hoverTimer.current);
    activeCompany.current = null;
    setTooltip(null);
  }

  return (
    <div className="table-page-shell">
      <div className="shell">
        <header className="topbar">
          <Link to="/" className="brand">
            <span className="brand-mark">J</span>
            <span>JobScout</span>
          </Link>
          <Link to="/" className="back-link">&larr; Back to dashboard</Link>
        </header>

        <h1>All jobs</h1>
        <p className="page-sub">Hover a company name for a quick research snapshot. Click a row to open it in the dashboard.</p>

        <input
          className="search-box"
          type="text"
          placeholder="Search jobs, skills, companies..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Role</th>
                <th>Description</th>
                <th>Company</th>
                <th>Location</th>
                <th>Platform</th>
                <th>Posted</th>
                <th>Score</th>
                <th>Link</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan={8}><div className="empty-state">No jobs match the current search.</div></td></tr>
              ) : (
                rows.map((job) => {
                  const description = (job.description || '').replace(/\s+/g, ' ').trim();
                  return (
                    <tr key={job.id} onClick={() => navigate(`/?job=${job.id}`)}>
                      <td className="job-title-cell">{job.title || 'Untitled role'}</td>
                      <td className="description-cell" title={description}>
                        {description || 'No description available.'}
                      </td>
                      <td
                        className="company-cell"
                        onMouseEnter={(event) => handleMouseEnter(job.company || '', event)}
                        onMouseLeave={handleMouseLeave}
                      >
                        <span className="company-name">{job.company || 'Company'}</span>
                      </td>
                      <td>{job.location || 'Remote'}</td>
                      <td><span className={platformClass(job.platform)}>{platformLabel(job.platform)}</span></td>
                      <td>{formatDate(job.posted_at)}</td>
                      <td><span className="score">{scoreFor(job)}%</span></td>
                      <td>
                        {job.url && (
                          <a
                            className="open-link"
                            href={job.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            title="Open job posting"
                            onClick={(event) => event.stopPropagation()}
                          >
                            &#8599;
                          </a>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {tooltip && <CompanyTooltip name={tooltip.name} profile={tooltip.profile} position={tooltip.position} />}
    </div>
  );
}
