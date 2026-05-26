const PREFIX = 'mytaba.prefs';

function storageKey(username, name) {
  const user = (username || 'guest').trim() || 'guest';
  return `${PREFIX}.${user}.${name}`;
}

export function loadUserPreference(username, name, allowedValues, defaultValue) {
  try {
    const raw = localStorage.getItem(storageKey(username, name));
    if (raw && allowedValues.includes(raw)) return raw;
  } catch {
    /* ignore quota / private mode */
  }
  return defaultValue;
}

export function saveUserPreference(username, name, value) {
  try {
    localStorage.setItem(storageKey(username, name), value);
  } catch {
    /* ignore */
  }
}

export function loadUserPreferenceJson(username, name, defaultValue) {
  try {
    const raw = localStorage.getItem(storageKey(username, name));
    if (raw) return JSON.parse(raw);
  } catch {
    /* ignore */
  }
  return defaultValue;
}

export function saveUserPreferenceJson(username, name, value) {
  try {
    localStorage.setItem(storageKey(username, name), JSON.stringify(value));
  } catch {
    /* ignore */
  }
}
