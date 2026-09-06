async function request(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // response wasn't JSON; keep the generic message
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  listJobs: () => request('/jobs/'),
  listResumes: () => request('/resumes/'),
  uploadResume: (formData) => request('/resumes/', { method: 'POST', body: formData }),
  deleteResume: (resumeId) => request(`/resumes/${resumeId}`, { method: 'DELETE' }),
  companyResearch: (name) => request(`/jobs/company-research?name=${encodeURIComponent(name)}`),
  salaryEstimate: (company, title) =>
    request(`/jobs/salary-estimate?company=${encodeURIComponent(company)}&title=${encodeURIComponent(title)}`),
  generateCv: (resumeId, jobId) =>
    request('/cv/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume_id: resumeId, job_id: jobId }),
    }),
  getSavedCv: async (resumeId, jobId) => {
    try {
      return await request(`/cv/?resume_id=${resumeId}&job_id=${jobId}`);
    } catch {
      return null;
    }
  },
  sendChatMessage: (message) =>
    request('/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    }),
  authStatus: () => request('/auth/status'),
  login: (password) =>
    request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    }),
  logout: () => request('/auth/logout', { method: 'POST' }),
};
