const REPO = 'Zenkjt/tangthu-opds';
const BRANCH = 'main';
const GITHUB_API = 'https://api.github.com';
const RAW_BASE = 'https://raw.githubusercontent.com/Zenkjt/tangthu-opds/main';
const UA = 'TangThu-News/1.0 (+https://tangthu.pages.dev)';

export function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8' }
  });
}

export function corsHeaders(origin) {
  const allowed = 'https://tangthu.pages.dev';
  return origin === allowed ? {
    'access-control-allow-origin': allowed,
    'access-control-allow-methods': 'POST, OPTIONS',
    'access-control-allow-headers': 'content-type',
    'vary': 'Origin'
  } : {};
}

export function withCors(response, origin) {
  const headers = new Headers(response.headers);
  for (const [k, v] of Object.entries(corsHeaders(origin))) headers.set(k, v);
  return new Response(response.body, { status: response.status, headers });
}

export function normalizeUrl(value) {
  try {
    const u = new URL(String(value || '').trim());
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return '';
    u.hash = '';
    if (u.pathname.length > 1) u.pathname = u.pathname.replace(/\/+$/, '');
    return u.toString();
  } catch (_) {
    return '';
  }
}

function decodeHtml(value) {
  return String(value || '')
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&quot;/g, '"').replace(/&apos;/g, "'")
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ').trim();
}

function attrs(tag) {
  const out = {};
  const re = /([:\w-]+)\s*=\s*["']([^"']*)["']/g;
  let m;
  while ((m = re.exec(tag))) out[m[1].toLowerCase()] = decodeHtml(m[2]);
  return out;
}

function metaValue(html, wanted) {
  const re = /<meta\b[^>]*>/gi;
  let m;
  while ((m = re.exec(html))) {
    const a = attrs(m[0]);
    if ((a.property || a.name || '').toLowerCase() === wanted) return a.content || '';
  }
  return '';
}

function cleanTitle(value) {
  return decodeHtml(value).replace(/^[-|–—:\s]+|[-|–—:\s]+$/g, '').trim();
}

function fallbackSiteName(url) {
  const host = new URL(url).hostname.toLowerCase().replace(/^www\./, '');
  const first = host.split('.')[0];
  const known = { vnexpress: 'VnExpress', dantri: 'Dân trí', tuoitre: 'Tuổi Trẻ', thanhnien: 'Thanh Niên', nld: 'Người Lao Động', bbc: 'BBC', cnn: 'CNN', npr: 'NPR' };
  if (known[first]) return known[first];
  return first.replace(/[-_]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function makeSourceName(url, html) {
  const site = cleanTitle(metaValue(html, 'og:site_name')) || fallbackSiteName(url);
  let title = cleanTitle(metaValue(html, 'og:title'));
  if (!title) {
    const m = /<title\b[^>]*>([\s\S]*?)<\/title>/i.exec(html);
    title = cleanTitle(m ? m[1] : '');
  }
  if (!title) return site;

  const withoutSite = cleanTitle(title.replace(new RegExp('(?:^|\\s*[-|–—:]\\s*)' + escapeRegExp(site) + '$', 'i'), ''));
  if (!withoutSite || withoutSite.toLowerCase() === site.toLowerCase()) return site;

  // Remove common SEO boilerplate while retaining the actual section/topic.
  const topic = withoutSite
    .replace(/\s*[-|–—]\s*tin tức mới nhất 24h qua\s*$/i, '')
    .replace(/\s*[-|–—]\s*báo tiếng việt.*$/i, '')
    .trim();
  return topic ? `${site} — ${topic}` : site;
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export async function fetchSourceInfo(url) {
  const response = await fetch(url, {
    headers: { 'user-agent': UA, 'accept': 'text/html,application/xhtml+xml' },
    redirect: 'follow'
  });
  if (!response.ok) throw new Error(`Nguồn trả HTTP ${response.status}`);
  const html = (await response.text()).slice(0, 500000);
  return { name: makeSourceName(url, html) };
}

export async function rawJson(path) {
  const r = await fetch(`${RAW_BASE}/${path}`, { headers: { 'user-agent': UA } });
  if (!r.ok) throw new Error(`Không đọc được ${path}: HTTP ${r.status}`);
  return r.json();
}

export async function createIssue(env, title, body) {
  if (!env.GITHUB_TOKEN) throw new Error('Cloudflare secret GITHUB_TOKEN chưa được cấu hình');
  const r = await fetch(`${GITHUB_API}/repos/${REPO}/issues`, {
    method: 'POST',
    headers: {
      'accept': 'application/vnd.github+json',
      'authorization': `Bearer ${env.GITHUB_TOKEN}`,
      'x-github-api-version': '2026-03-10',
      'content-type': 'application/json',
      'user-agent': UA
    },
    body: JSON.stringify({ title, body })
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.message || `GitHub HTTP ${r.status}`);
  return data;
}
