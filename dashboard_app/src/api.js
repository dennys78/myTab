function getCookie(name) {
  return document.cookie
    .split('; ')
    .find(row => row.startsWith(`${name}=`))
    ?.split('=')[1];
}

export function apiFetch(url, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers || {});

  if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
    const csrfToken = getCookie('csrftoken');
    if (csrfToken) headers.set('X-CSRFToken', decodeURIComponent(csrfToken));
  }

  return fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers,
  });
}
