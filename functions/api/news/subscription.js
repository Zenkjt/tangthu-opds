import { json, withCors, rawJson, createIssue } from '../../lib/news.js';

export async function onRequestOptions(context) {
  return withCors(new Response(null, { status: 204 }), context.request.headers.get('origin'));
}

export async function onRequestPost(context) {
  const origin = context.request.headers.get('origin');
  if (origin && origin !== 'https://tangthu.pages.dev') return json({ error: 'Origin không được phép' }, 403);

  try {
    const body = await context.request.json();
    const branchId = String(body.branch_id || '').trim();
    const sourceId = String(body.source_id || '').trim();
    const articleCount = Number(body.article_count);
    const mode = String(body.edition_mode || '');
    if (!branchId || !sourceId || !Number.isInteger(articleCount) || articleCount < 5 || articleCount > 25 || !['text', 'images'].includes(mode)) {
      return withCors(json({ error: 'Thông tin đăng ký không hợp lệ' }, 400), origin);
    }

    const [branches, registry] = await Promise.all([
      rawJson('config/branches.json'),
      rawJson('config/config_news_sources.json')
    ]);
    const branch = (Array.isArray(branches.branches) ? branches.branches : []).find(b => b.id === branchId && b.enabled !== false);
    const source = (Array.isArray(registry.sources) ? registry.sources : []).find(s => s.id === sourceId && s.enabled !== false);
    if (!branch) return withCors(json({ error: 'Tủ sách không tồn tại hoặc đang bị tạm dừng' }, 400), origin);
    if (!source) return withCors(json({ error: 'Nguồn tin không tồn tại hoặc đã tắt' }, 400), origin);

    const subscriptions = await rawJson('config/config_news_subscriptions.json');
    const existing = (Array.isArray(subscriptions.subscriptions) ? subscriptions.subscriptions : [])
      .find(s => s.branch_id === branchId && s.source_id === sourceId && s.enabled !== false);
    if (existing) {
      return withCors(json({ ok: true, existing: true }), origin);
    }

    const issue = await createIssue(
      context.env,
      `[TIN TỨC SUB] ${source.name}`,
      `- Tủ sách ID: ${branchId}\n- Source ID: ${sourceId}\n- Số bài: ${articleCount}\n- Chế độ: ${mode}\n- Hành động: add`
    );
    return withCors(json({ ok: true, issue_url: issue.html_url || '' }, 201), origin);
  } catch (error) {
    return withCors(json({ error: error.message || 'Lỗi máy chủ' }, 500), origin);
  }
}
