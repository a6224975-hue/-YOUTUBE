/* 「粹」手作烘焙 Service Worker
 * 策略：
 *  - 預先快取 App Shell (index.html、manifest、圖示) 與 CDN 資源
 *  - 頁面導覽：網路優先，離線時回退到快取的 index.html
 *  - 同源靜態檔：快取優先 + 背景更新
 *  - 跨來源 (Tailwind / FontAwesome / Google Fonts / 圖片)：Stale-While-Revalidate
 *  修改任何檔案後，請更新 VERSION 讓使用者取得新版。
 */
const VERSION = 'v1.0.3';
const SHELL_CACHE = `cui-shell-${VERSION}`;
const RUNTIME_CACHE = `cui-runtime-${VERSION}`;

const SHELL_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/maskable-192.png',
  './icons/apple-touch-icon.png',
  './icons/favicon-32.png',
  './icons/favicon.ico'
];

// 網站圖片 (Logo、情境照、商品與禮盒照)。逐一預載，單張失敗不會讓 Service Worker 安裝失敗
const IMAGE_ASSETS = [
  'logo-mark.png', 'hero-brunch.jpg', 'gift-showcase.jpg',
  'product-pudding.jpg', 'product-cookies.jpg', 'product-snowq.jpg', 'product-nougat.jpg',
  'giftbox-small.jpg', 'giftbox-classic.jpg', 'giftbox-deluxe.jpg'
].map((f) => `./images/${f}`);

// 跨來源資源 (安裝時以 no-cors 預載，離線也能顯示樣式與圖示)
const CDN_ASSETS = [
  'https://cdn.tailwindcss.com',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
  'https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap'
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const shell = await caches.open(SHELL_CACHE);
    await shell.addAll(SHELL_ASSETS);

    // 圖片預載：單張失敗 (例如檔案尚未放入) 不影響安裝
    await Promise.all(IMAGE_ASSETS.map(async (url) => {
      try { await shell.add(url); } catch (_) {}
    }));

    // CDN 預載失敗不應阻擋安裝
    await Promise.all(CDN_ASSETS.map(async (url) => {
      try {
        const res = await fetch(new Request(url, { mode: 'no-cors' }));
        await shell.put(url, res);
      } catch (_) { /* 離線或被擋下，之後執行時再快取 */ }
    }));
    // 不自動 skipWaiting：由頁面在使用者同意更新後送出 SKIP_WAITING
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keep = [SHELL_CACHE, RUNTIME_CACHE];
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k.startsWith('cui-') && !keep.includes(k)).map((k) => caches.delete(k)));
    if (self.registration.navigationPreload) {
      try { await self.registration.navigationPreload.enable(); } catch (_) {}
    }
    await self.clients.claim();
  })());
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (!/^https?:$/.test(url.protocol)) return;

  // 分析/追蹤服務 (Google Analytics / Tag Manager) 與 YouTube 播放器一律直連網路，不經快取
  // (影片封面圖 i.ytimg.com 不在此列，仍會被快取，離線時封面可正常顯示)
  if (/(^|\.)(googletagmanager|google-analytics|analytics\.google|doubleclick)\.(com|net)$/.test(url.hostname)) return;
  if (/(^|\.)(youtube|youtube-nocookie)\.com$|(^|\.)googlevideo\.com$|^youtu\.be$/.test(url.hostname)) return;

  // 1) 頁面導覽：網路優先 → 離線回退 index.html
  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const preload = await event.preloadResponse;
        if (preload) return preload;
        const fresh = await fetch(request);
        const cache = await caches.open(SHELL_CACHE);
        cache.put('./index.html', fresh.clone());
        return fresh;
      } catch (_) {
        return (await caches.match('./index.html', { ignoreSearch: true })) ||
               (await caches.match('./', { ignoreSearch: true })) ||
               new Response('目前離線，請連上網路後再試。', {
                 status: 503,
                 headers: { 'Content-Type': 'text/plain; charset=utf-8' }
               });
      }
    })());
    return;
  }

  // 2) 同源靜態檔：快取優先 + 背景更新
  if (url.origin === self.location.origin) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // 3) 跨來源：Stale-While-Revalidate
  event.respondWith(staleWhileRevalidate(request));
});

async function cacheFirst(request) {
  const cached = await caches.match(request, { ignoreSearch: true });
  if (cached) {
    // 背景更新
    fetch(request).then(async (res) => {
      if (res && res.ok) (await caches.open(SHELL_CACHE)).put(request, res);
    }).catch(() => {});
    return cached;
  }
  try {
    const res = await fetch(request);
    if (res && res.ok) (await caches.open(RUNTIME_CACHE)).put(request, res.clone());
    return res;
  } catch (_) {
    return new Response('', { status: 504 });
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(RUNTIME_CACHE);
  const cached = (await cache.match(request)) || (await caches.match(request));
  const network = fetch(request).then((res) => {
    // 允許 opaque (type === 'opaque') 的跨來源回應
    if (res && (res.ok || res.type === 'opaque')) cache.put(request, res.clone());
    return res;
  }).catch(() => null);

  if (cached) return cached;
  const res = await network;
  return res || new Response('', { status: 504 });
}
