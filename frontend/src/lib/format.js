export function scoreFor(job) {
  const len = (job.title || '').length + (job.company || '').length;
  return Math.min(98, Math.max(65, Math.round(72 + (len % 18))));
}

export function isRemote(job) {
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
