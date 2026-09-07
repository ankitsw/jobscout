import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import JobsPanel from '../components/JobsPanel.jsx';
import DetailPanel from '../components/DetailPanel.jsx';
import ChatPanel from '../components/ChatPanel.jsx';
import ResumeManager from '../components/ResumeManager.jsx';
import CvViewer from '../components/CvViewer.jsx';
import { api } from '../lib/api.js';
import { DEFAULT_FILTERS, filterAndSortJobs } from '../lib/filters.js';

export default function DashboardPage() {
  const [searchParams] = useSearchParams();
  const [jobs, setJobs] = useState([]);
  const [resumes, setResumes] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [selectedResumeId, setSelectedResumeId] = useState(null);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [filterBarOpen, setFilterBarOpen] = useState(false);
  const [resumeManagerOpen, setResumeManagerOpen] = useState(false);
  const [savedCv, setSavedCv] = useState(null); // { cv } for the current job+resume pair, if one has been generated
  const [cvViewerOpen, setCvViewerOpen] = useState(false);
  const [matchScores, setMatchScores] = useState({}); // { [jobId]: 0-100 }, only populated once a resume is selected
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Hi! I can help shortlist roles, tailor your CV, and suggest strongest angles for each application.' },
  ]);
  const [detailExtras, setDetailExtras] = useState({
    classification: '', rating: null, reviewsCount: null, salary: null, description: '',
  });

  const companyProfileCache = useRef(new Map());
  const salaryEstimateCache = useRef(new Map());
  const hasAppliedInitialSelection = useRef(false);

  function appendMessage(role, text) {
    setMessages((prev) => [...prev, { role, text }]);
  }

  async function loadJobs() {
    const data = await api.listJobs();
    const list = Array.isArray(data) ? data : [];
    setJobs(list);
    if (!hasAppliedInitialSelection.current && list.length) {
      hasAppliedInitialSelection.current = true;
      const requestedId = searchParams.get('job');
      const match = requestedId && list.find((job) => String(job.id) === requestedId);
      setSelectedJobId(match ? Number(requestedId) : Number(list[0].id));
    }
  }

  async function loadResumes() {
    const data = await api.listResumes();
    setResumes(Array.isArray(data) ? data : []);
  }

  useEffect(() => {
    Promise.all([loadJobs(), loadResumes()]).catch((error) => {
      console.error('Initial load failed', error);
      appendMessage('assistant', 'The app is loading. Check the backend or database connection.');
    });
    // run once on mount; loadJobs reads searchParams only for the first selection
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedJob = useMemo(
    () => jobs.find((job) => Number(job.id) === Number(selectedJobId)) || null,
    [jobs, selectedJobId],
  );

  const visibleJobs = useMemo(
    () => filterAndSortJobs(jobs, search, filters, matchScores),
    [jobs, search, filters, matchScores],
  );

  // Real match scores are resume-scoped - fetch (or clear) the whole set
  // whenever the selected resume changes, rather than faking a score with
  // no resume behind it.
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

  // A previously generated CV is tied to one (resume, job) pair - reload it
  // (or clear it) whenever either side of that pair changes, so switching
  // jobs/resumes never shows a stale CV, and switching back doesn't require
  // paying for another LLM call.
  useEffect(() => {
    setCvViewerOpen(false);
    if (!selectedJobId || !selectedResumeId) {
      setSavedCv(null);
      return;
    }
    let cancelled = false;
    api.getSavedCv(selectedResumeId, selectedJobId).then((result) => {
      if (!cancelled) setSavedCv(result);
    });
    return () => { cancelled = true; };
  }, [selectedJobId, selectedResumeId]);

  // Fetch company profile + salary estimate whenever the selected job changes.
  useEffect(() => {
    if (!selectedJob) {
      setDetailExtras({ classification: '', rating: null, reviewsCount: null, salary: null, description: '' });
      return;
    }

    let cancelled = false;
    const jobDescription = (selectedJob.description || '').trim();
    setDetailExtras({
      classification: '', rating: null, reviewsCount: null, salary: null,
      description: jobDescription || 'Looking up the company…',
    });

    async function fetchProfile(companyName) {
      if (!companyName) return null;
      if (companyProfileCache.current.has(companyName)) return companyProfileCache.current.get(companyName);
      let profile = null;
      try {
        profile = await api.companyResearch(companyName);
      } catch {
        profile = null;
      }
      companyProfileCache.current.set(companyName, profile);
      return profile;
    }

    async function fetchSalary(companyName, jobTitle) {
      const cacheKey = `${companyName}::${jobTitle}`;
      if (salaryEstimateCache.current.has(cacheKey)) return salaryEstimateCache.current.get(cacheKey);
      let estimate = null;
      try {
        estimate = await api.salaryEstimate(companyName, jobTitle);
      } catch {
        estimate = null;
      }
      salaryEstimateCache.current.set(cacheKey, estimate);
      return estimate;
    }

    const companyName = selectedJob.company || '';
    Promise.all([
      fetchProfile(companyName),
      companyName && selectedJob.title ? fetchSalary(companyName, selectedJob.title) : null,
    ]).then(([profile, salary]) => {
      if (cancelled) return;
      const hasSalary = salary && salary.typical_min_ctc != null && salary.typical_max_ctc != null;
      setDetailExtras({
        classification: profile?.classification || '',
        rating: profile?.ambitionbox_rating ?? null,
        reviewsCount: profile?.ambitionbox_reviews_count ?? null,
        salary: hasSalary ? salary : null,
        description: jobDescription || (profile?.description
          ? `No job description available. About ${companyName}:\n\n${profile.description}`
          : 'No description available.'),
      });
    });

    return () => { cancelled = true; };
  }, [selectedJob]);

  async function handleRefresh() {
    try {
      await loadJobs();
    } catch (error) {
      console.error('Refresh failed', error);
    }
  }

  async function handleGenerateCv() {
    if (!selectedJobId) {
      alert('Select a job first.');
      return;
    }
    if (!selectedResumeId) {
      alert('Select a resume before generating a tailored CV.');
      return;
    }
    try {
      const result = await api.generateCv(selectedResumeId, selectedJobId);
      setSavedCv(result);
      setCvViewerOpen(true);
      appendMessage('assistant', 'CV draft generated successfully. Opened it for review.');
    } catch (error) {
      alert(error.message || 'Unable to generate CV.');
    }
  }

  function handleViewCv() {
    if (savedCv) setCvViewerOpen(true);
  }

  async function handleDeleteJob(jobId) {
    try {
      await api.deleteJob(jobId);
      setJobs((prev) => prev.filter((job) => Number(job.id) !== Number(jobId)));
      if (Number(selectedJobId) === Number(jobId)) setSelectedJobId(null);
    } catch (error) {
      alert(error.message || 'Unable to delete job.');
    }
  }

  async function handleSendChat(text) {
    appendMessage('user', text);
    try {
      const data = await api.sendChatMessage(text);
      appendMessage('assistant', data.response || 'No response from assistant.');
    } catch (error) {
      appendMessage('assistant', 'The assistant hit an error. Please try again.');
    }
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
      const result = await api.uploadResume(formData);
      await loadResumes();
      setSelectedResumeId(Number(result.id));
      appendMessage('assistant', `Uploaded "${result.name || `Resume #${result.id}`}". It is now ready for tailored CV generation.`);
    } catch (error) {
      alert(error.message || 'Resume upload failed.');
    }
  }

  async function handleDeleteResume(resumeId) {
    try {
      await api.deleteResume(resumeId);
      await loadResumes();
      if (Number(selectedResumeId) === Number(resumeId)) setSelectedResumeId(null);
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

  return (
    <div className="dashboard-shell">
      <div className="shell">
        <header className="topbar">
          <div className="brand">
            <span className="brand-mark">J</span>
            <span>JobScout</span>
          </div>
          <div className="nav-actions">
            <button className="ghost-button" onClick={() => setResumeManagerOpen(true)}>Resumes</button>
            <button className="ghost-button" onClick={handleRefresh}>Refresh</button>
          </div>
        </header>

        <main className="dashboard">
          <JobsPanel
            visibleJobs={visibleJobs}
            selectedJobId={selectedJobId}
            onSelectJob={setSelectedJobId}
            search={search}
            onSearchChange={setSearch}
            filters={filters}
            onFiltersChange={setFilters}
            filterBarOpen={filterBarOpen}
            onToggleFilterBar={() => setFilterBarOpen((open) => !open)}
            matchScores={matchScores}
          />

          <DetailPanel
            job={selectedJob}
            detailExtras={detailExtras}
            resumes={resumes}
            selectedResumeId={selectedResumeId}
            onSelectResume={setSelectedResumeId}
            onUploadResume={handleUploadResume}
            onGenerateCv={handleGenerateCv}
            hasCv={Boolean(savedCv)}
            onViewCv={handleViewCv}
            onDeleteJob={handleDeleteJob}
            matchScores={matchScores}
          />

          <ChatPanel messages={messages} onSend={handleSendChat} />
        </main>
      </div>

      {resumeManagerOpen && (
        <ResumeManager
          resumes={resumes}
          onUpload={handleUploadResume}
          onDelete={handleDeleteResume}
          onRename={handleRenameResume}
          onClose={() => setResumeManagerOpen(false)}
        />
      )}

      {cvViewerOpen && savedCv && (
        <CvViewer
          job={selectedJob}
          cv={savedCv.cv}
          onClose={() => setCvViewerOpen(false)}
        />
      )}
    </div>
  );
}
