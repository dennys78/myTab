self.addEventListener('push', (event) => {
  let payload = {
    title: 'myTab',
    body: 'Nuova attività da contabilizzare',
    url: '/?view=acquisisci-ai',
    tag: 'mytab-draft',
  };
  try {
    if (event.data) {
      payload = { ...payload, ...event.data.json() };
    }
  } catch (_) {
    /* ignore malformed payload */
  }

  const iconUrl = new URL('/pwa-192x192.png', self.location.origin).href;
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: iconUrl,
      badge: iconUrl,
      tag: payload.tag || 'mytab-draft',
      data: { url: payload.url || '/?view=acquisisci-ai' },
    }),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || '/?view=acquisisci-ai';
  const absoluteUrl = new URL(targetUrl, self.location.origin).href;

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.startsWith(self.location.origin) && 'focus' in client) {
          if (typeof client.navigate === 'function') {
            return client.navigate(absoluteUrl).then(() => client.focus());
          }
          return client.focus().then(() => {
            client.postMessage({ type: 'NAVIGATE', url: absoluteUrl });
          });
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(absoluteUrl);
      }
      return undefined;
    }),
  );
});
