const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const listeners = {};
const cacheEntries = new Map();
const cache = {
  async addAll() {},
  async match(request) { return cacheEntries.get(typeof request === 'string' ? request : request.url); },
  async put(request, response) { cacheEntries.set(typeof request === 'string' ? request : request.url, response); }
};
const cacheStorage = {
  async open() { return cache; },
  async keys() { return ['treino-planner-v10']; },
  async delete() { return true; }
};
let currentVersion = 'new-app-js';
let online = true;
let fetchCalls = 0;
let lastFetchOptions = null;
const context = {
  self: {
    addEventListener(type, listener) { listeners[type] = listener; },
    async skipWaiting() {},
    clients: { async claim() {} }
  },
  caches: cacheStorage,
  location: { origin: 'http://localhost:8000' },
  URL,
  Response: { error() { return { offlineError: true }; } },
  fetch: async (_request, options) => {
    fetchCalls += 1;
    lastFetchOptions = options;
    if (!online) throw new Error('offline');
    return { ok: true, version: currentVersion, clone() { return this; } };
  }
};

vm.runInNewContext(fs.readFileSync(require.resolve('../sw.js'), 'utf8'), context);

async function requestThroughWorker(url, mode = 'cors') {
  let responsePromise;
  const event = {
    request: { method: 'GET', url, mode },
    respondWith(promise) { responsePromise = promise; }
  };
  listeners.fetch(event);
  return responsePromise;
}

(async () => {
  const assetPaths = ['/app.js', '/rest-timer.js', '/index.html'];
  for (const assetPath of assetPaths) {
    const assetUrl = 'http://localhost:8000' + assetPath;
    currentVersion = 'new-' + assetPath.slice(1);
    cacheEntries.set(assetUrl, { version: 'old-' + assetPath.slice(1) });

    const fresh = await requestThroughWorker(assetUrl, assetPath === '/index.html' ? 'navigate' : 'cors');
    assert.equal(fresh.version, currentVersion, assetPath + ' must return the updated network asset');
    assert.equal(lastFetchOptions.cache, 'no-cache', assetPath + ' must revalidate the browser HTTP cache');
    assert.equal(cacheEntries.get(assetUrl).version, currentVersion, assetPath + ' must replace its offline cache entry');
  }
  assert.equal(fetchCalls, assetPaths.length);

  online = false;
  const appUrl = 'http://localhost:8000/app.js';
  const offline = await requestThroughWorker(appUrl);
  assert.equal(offline.version, 'new-app.js', 'offline request must keep serving the latest cached asset');

  let apiHandled = false;
  listeners.fetch({
    request: { method: 'GET', url: 'http://localhost:8000/api/plans', mode: 'cors' },
    respondWith() { apiHandled = true; }
  });
  assert.equal(apiHandled, false, 'API requests must remain outside the static asset cache');

  console.log('3 service worker update/offline tests passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
