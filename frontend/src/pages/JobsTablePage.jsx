import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import CompanyTooltip from '../components/CompanyTooltip.jsx';
import FilterBar from '../components/FilterBar.jsx';
import ResumeManager from '../components/ResumeManager.jsx';
import { api } from '../lib/api.js';
import { matchScoreFor, formatDate, platformLabel, platformClass } from '../lib/format.js';
import { DEFAULT_FILTERS, filterAndSortJobs } from '../lib/filters.js';
import { getLastResumeId, setLastResumeId } from '../lib/lastResume.js';

const HOVER_DELAY_MS = 250;

export default function JobsTablePage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [resumes, setResumes] = useState([]);
  const [selectedResumeId, setSelectedResumeId] = useState(null);
  const [matchScores, setMatchScores] = useState({});
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [filterBarOpen, setFilterBarOpen] = useState(false);
  const [resumeManagerOpen, setResumeManagerOpen] = useState(false);
  const [tooltip, setTooltip] = useState(null); // { name, position, profile }

  const profileCache = useRef(new Map());
  const hoverTimer = useRef(null);
  const activeCompany = useRef(null);

  useEffect(() => {
    api.listJobs()
      .then((data) => setJobs(Array.isArray(data) ? data : []))
      .catch(() => setJobs([]));
    loadResumes();
  }, []);

  async function loadResumes() {
    const data = await api.listResumes();
    const list = Array.isArray(data) ? data : [];
    setResumes(list);
    setSelectedResumeId((current) => {
      if (current) return current;
      const lastId = getLastResumeId();
      if (lastId && list.some((resume) => Number(resume.id) === lastId)) return lastId;
      // No remembered choice (or it no longer exists) - default to the most
      // recently uploaded resume (list is already newest-first) rather than
      // leaving scores blank until someone manually picks one.
      return list[0]?.id ?? current;
    });
  }

  function handleSelectResume(id) {
    setSelectedResumeId(id);
    setLastResumeId(id);
  }

  async function handleUploadResume(file, name = '') {
    if (!file) {
      alert('Choose a PDF file first.');
      return;
    }
    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', name);
    try {
      await api.uploadResume(formData);
      await loadResumes();
    } catch (error) {
      alert(error.message || 'Resume upload failed.');
    }
  }

  async function handleDeleteResume(resumeId) {
    try {
      await api.deleteResume(resumeId);
      await loadResumes();
      if (Number(selectedResumeId) === Number(resumeId)) handleSelectResume(null);
    } catch (error) {
      alert(error.message || 'Unable to delete resume.');
    }
  }

  async function handleRenameResume(resumeId, name) {
    try {
      await api.renameResume(resumeId, name);
      await loadResumes();
    } catch (error) {
      alert(error.message || 'Unable to rename resume.');
    }
  }

  async function handleDeleteJob(jobId) {
    try {
      await api.deleteJob(jobId);
      setJobs((prev) => prev.filter((job) => Number(job.id) !== Number(jobId)));
    } catch (error) {
      alert(error.message || 'Unable to delete job.');
    }
  }

  useEffect(() => {
    function hide() {
      clearTimeout(hoverTimer.current);
      activeCompany.current = null;
      setTooltip(null);
    }
    window.addEventListener('scroll', hide, true);
    return () => window.removeEventListener('scroll', hide, true);
  }, []);

  const rows = useMemo(
    () => filterAndSortJobs(jobs, search, filters, matchScores),
    [jobs, search, filters, matchScores],
  );

  useEffect(() => {
    if (!selectedResumeId) {
      setMatchScores({});
      return;
    }
    let cancelled = false;
    api.quickMatchScores(selectedResumeId)
      .then((scores) => { if (!cancelled) setMatchScores(scores || {}); })
      .catch(() => { if (!cancelled) setMatchScores({}); });
    return () => { cancelled = true; };
  }, [selectedResumeId]);

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
          <div className="nav-actions">
            <button className="ghost-button" onClick={() => setResumeManagerOpen(true)}>Resumes</button>
            <Link to="/" className="back-link">&larr; Back to dashboard</Link>
          </div>
        </header>

        <h1>All jobs</h1>
        <p className="page-sub">Hover a company name for a quick research snapshot. Click a row to open it in the dashboard.</p>

        <div className="table-page-toolbar">
          <input
            className="search-box"
            type="text"
            placeholder="Search jobs, skills, companies..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <select
            className="resume-match-select"
            value={selectedResumeId ?? ''}
            onChange={(event) => handleSelectResume(event.target.value ? Number(event.target.value) : null)}
          >
            <option value="">Match against a resume…</option>
            {resumes.map((resume) => (
              <option key={resume.id} value={resume.id}>{resume.name || `Resume #${resume.id}`}</option>
            ))}
          </select>
          <button className="ghost-button small" onClick={() => setFilterBarOpen((open) => !open)}>Filter</button>
        </div>

        {filterBarOpen && <FilterBar filters={filters} onChange={setFilters} />}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Role</th>
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
                <tr><td colSpan={7}><div className="empty-state">No jobs match the current filters.</div></td></tr>
              ) : (
                rows.map((job) => {
                  const description = (job.description || '').replace(/\s+/g, ' ').trim();
                  return (
                    <tr key={job.id} onClick={() => navigate(`/?job=${job.id}`)} title={description}>
                      <td className="job-title-cell">{job.title || 'Untitled role'}</td>
                      <td
                        className="company-cell"
                        onMouseEnter={(event) => handleMouseEnter(job.company || '', event)}
                        onMouseLeave={handleMouseLeave}
                      >
                        <span className="company-name">{job.company || 'Company'}</span>
                      </td>
                      <td className="location-cell">{job.location || 'Remote'}</td>
                      <td><span className={platformClass(job.platform)}>{platformLabel(job.platform)}</span></td>
                      <td>{formatDate(job.posted_at)}</td>
                      <td>
                        {(() => {
                          const score = matchScoreFor(job, matchScores);
                          return (
                            <span className={`score${score == null ? ' score-empty' : ''}`} title={score == null ? 'Pick a resume to see match score' : undefined}>
                              {score == null ? '—' : `${score}%`}
                            </span>
                          );
                        })()}
                      </td>
                      <td>
                        <div className="row-actions">
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
                          <button
                            className="icon-button danger"
                            title="Delete this job"
                            onClick={(event) => {
                              event.stopPropagation();
                              if (confirm(`Delete "${job.title || 'this job'}"? This cannot be undone.`)) {
                                handleDeleteJob(job.id);
                              }
                            }}
                          >
                            &#128465;
                          </button>
                        </div>
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

      {resumeManagerOpen && (
        <ResumeManager
          resumes={resumes}
          onUpload={handleUploadResume}
          onDelete={handleDeleteResume}
          onRename={handleRenameResume}
          onClose={() => setResumeManagerOpen(false)}
        />
      )}
    </div>
  );
}
