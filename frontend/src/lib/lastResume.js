// Remembers which resume was last used for match scoring, per browser, so
// scores don't require re-picking a resume on every page load/navigation.
const KEY = 'jobscout:lastResumeId';

export function getLastResumeId() {
  try {
    const value = localStorage.getItem(KEY);
    return value ? Number(value) : null;
  } catch {
    return null;
  }
}

export function setLastResumeId(id) {
  try {
    if (id) localStorage.setItem(KEY, String(id));
    else localStorage.removeItem(KEY);
  } catch {
    // localStorage unavailable (private mode, etc.) - not selecting a
    // resume automatically next time isn't worth failing anything over.
  }
}
