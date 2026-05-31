const STORAGE_PREFIX = 'mytab_seen_telegram_drafts_';

export function seenDraftsStorageKey(companyId) {
  return `${STORAGE_PREFIX}${companyId || 'default'}`;
}

export function loadSeenDraftIds(companyId) {
  try {
    const raw = sessionStorage.getItem(seenDraftsStorageKey(companyId));
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch {
    return new Set();
  }
}

export function saveSeenDraftIds(companyId, ids) {
  const merged = new Set([...loadSeenDraftIds(companyId), ...ids]);
  sessionStorage.setItem(
    seenDraftsStorageKey(companyId),
    JSON.stringify([...merged].slice(-200)),
  );
  return merged;
}

export function markDraftsSeen(companyId, draftIds) {
  const ids = (draftIds || []).map((id) => Number(id)).filter(Boolean);
  if (!ids.length) return loadSeenDraftIds(companyId);
  return saveSeenDraftIds(companyId, ids);
}

export function filterUnseenDrafts(companyId, drafts) {
  const seen = loadSeenDraftIds(companyId);
  return (drafts || []).filter((d) => !seen.has(d.id));
}
