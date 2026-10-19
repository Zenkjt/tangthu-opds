import { json, withCors, normalizeUrl, fetchSourceInfo, rawJson, createIssue } from '../../lib/news.js';

export async function onRequestOptions(context) {
  return withCors(new Response(null, { status: 204 }), context.request.headers.get('origin'));
}

export async function onRequestPost(context) {
  const origin = context.request.headers.get('origin');
  if (origin && origin !== 'https://tangthu.pages.dev') return json({ error: 'Origin không được phép' }, 403);

  try {
    const body = await context.request.json();
    const action = body.action;
    const url = normalizeUrl(body.url);
    if (!url) return withCors(json({ error: 'URL không hợp lệ' }, 400), origin);

    const info = await fetchSourceInfo(url);
    const registry = await rawJson('config/config_news_sources.json');
    const sources = Array.isArray(registry.sources) ? registry.sources : [];
    const existing = sources.find(s => normalizeUrl(s.url) === url);

    if (action === 'check') {
      return withCors(json({ exists: !!existing, name: existing?.name || info.name, url }), origin);
    }

    if (action !== 'add') return withCors(json({ error: 'Action không hợp lệ' }, 400), origin);
    if (existing) return withCors(json({ exists: true, name: existing.name, url }), origin);

    const name = String(body.name || info.name).trim().slice(0, 200) || info.name;
    const issue = await createIssue(
      context.env,
      `[TIN TỨC] ${name}`,
      `- Tên nguồn: ${name}\n- URL: ${url}\n- Hành động: add`
    );
    return withCors(json({ ok: true, name, url, issue_url: issue.html_url || '' }, 201), origin);
  } catch (error) {
    return withCors(json({ error: error.message || 'Lỗi máy chủ' }, 500), origin);
  }
}
