import { matchScoreFor, isRemote, experienceBucket } from './format.js';

export const DEFAULT_FILTERS = {
  sortBy: 'score',
  platform: '',
  jobType: '',
  experienceLevel: '',
  remoteOnly: false,
};

export function filterAndSortJobs(jobs, search, filters, matchScores) {
  const query = search.trim().toLowerCase();
  let list = jobs.filter((job) => {
    if (filters.platform && job.platform !== filters.platform) return false;
    if (filters.jobType && job.job_type !== filters.jobType) return false;
    if (filters.experienceLevel && experienceBucket(job) !== filters.experienceLevel) return false;
    if (filters.remoteOnly && !isRemote(job)) return false;
    if (!query) return true;
    const haystack = `${job.title} ${job.company} ${job.location} ${job.description}`.toLowerCase();
    return haystack.includes(query);
  });

  list = list.slice().sort((a, b) => {
    if (filters.sortBy === 'newest') {
      return new Date(b.posted_at || 0) - new Date(a.posted_at || 0);
    }
    if (filters.sortBy === 'company') {
      return (a.company || '').localeCompare(b.company || '');
    }
    // "Best match" needs a selected resume to mean anything - without one,
    // there are no scores to sort by, so leave the list in whatever order
    // it arrived in rather than sorting on a made-up number.
    const scoreA = matchScoreFor(a, matchScores);
    const scoreB = matchScoreFor(b, matchScores);
    if (scoreA == null && scoreB == null) return 0;
    if (scoreA == null) return 1;
    if (scoreB == null) return -1;
    return scoreB - scoreA;
  });

  return list;
}
