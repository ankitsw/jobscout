// Real match scores come from GET /match/quick, keyed by job id, and only
// exist once a resume is selected - there is no meaningful "match" without
// something to match against. Returns null (not a fabricated number) when
// no score is available yet.
export function matchScoreFor(job, matchScores) {
  const score = matchScores?.[job.id];
  return typeof score === 'number' ? score : null;
}

export function isRemote(job) {
  if (job.workplace_type) return job.workplace_type === 'remote';
  return (job.location || '').toLowerCase().includes('remote');
}

export function experienceBucket(job) {
  const match = (job.experience_required || '').match(/\d+/);
  if (!match) return '';
  const years = Number(match[0]);
  if (years <= 1) return 'entry';
  if (years <= 4) return 'mid';
  if (years <= 7) return 'senior';
  return 'lead';
}

export function formatDate(value) {
  if (!value) return 'Recently';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Recently';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function formatLakhs(value) {
  return `₹${(value / 100000).toFixed(1)}L`;
}

const PLATFORM_LABELS = {
  linkedin: 'LinkedIn',
  indeed: 'Indeed',
  ats_greenhouse: 'Greenhouse',
  ats_lever: 'Lever',
  hirist: 'Hirist',
  internshala: 'Internshala',
};

export function platformLabel(platform) {
  return PLATFORM_LABELS[platform] || platform || 'Platform';
}

export function platformClass(platform) {
  return PLATFORM_LABELS[platform] ? `chip platform-${platform}` : 'chip';
}
