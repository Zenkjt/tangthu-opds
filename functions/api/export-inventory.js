import { json, withCors, rawJson } from '../lib/news.js';

const ALLOWED_ORIGIN = 'https://tangthu.pages.dev';

export async function onRequestOptions(context) {
  return withCors(new Response(null, { status: 204 }), context.request.headers.get('origin'));
}

export async function onRequestPost(context) {
  const origin = context.request.headers.get('origin');
  if (origin !== ALLOWED_ORIGIN) return json({ error: 'Origin không được phép' }, 403);

  try {
    const body = await context.request.json();
    const folderId = String(body.folder_id || '').trim();
    if (!/^[A-Za-z0-9_-]{10,}$/.test(folderId)) {
      return withCors(json({ error: 'Folder ID không hợp lệ.' }, 400), origin);
    }

    const appsScriptUrl = String(context.env.TANGTHU_APPS_SCRIPT_URL || '').trim();
    if (!appsScriptUrl) {
      return withCors(json({ error: 'Thiếu Cloudflare variable TANGTHU_APPS_SCRIPT_URL.' }, 503), origin);
    }
    let endpoint;
    try {
      endpoint = new URL(appsScriptUrl);
    } catch (_) {
      return withCors(json({ error: 'Cloudflare variable TANGTHU_APPS_SCRIPT_URL không hợp lệ.' }, 503), origin);
    }
    if (endpoint.protocol !== 'https:' || endpoint.hostname !== 'script.google.com' ||
        !/^\/macros\/s\/[^/]+\/exec$/.test(endpoint.pathname)) {
      return withCors(json({ error: 'Cloudflare variable TANGTHU_APPS_SCRIPT_URL không phải Web App hợp lệ.' }, 503), origin);
    }

    const config = await rawJson('config/branches.json');
    const shelf = (Array.isArray(config.branches) ? config.branches : [])
      .find(item => String(item.root_folder_id) === folderId && item.enabled !== false);
    if (!shelf) {
      return withCors(json({ error: 'Tủ đích không tồn tại hoặc đang bị tạm dừng.' }, 400), origin);
    }

    const token = String(context.env.TANGTHU_UPLOAD_TOKEN || '');
    if (!token) {
      return withCors(json({ error: 'Thiếu Cloudflare secret TANGTHU_UPLOAD_TOKEN.' }, 503), origin);
    }

    const response = await fetch(endpoint.toString(), {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      redirect: 'follow',
      body: JSON.stringify({ action: 'export_inventory', folder_id: folderId, token })
    });
    const raw = await response.text();
    let result;
    try {
      result = JSON.parse(raw);
    } catch (_) {
      throw new Error('Apps Script trả về dữ liệu không hợp lệ: ' + raw.slice(0, 300));
    }
    if (!response.ok || !result.ok) {
      return withCors(json({ error: result.error || `Apps Script HTTP ${response.status}` }, 502), origin);
    }
    return withCors(json(result), origin);
  } catch (error) {
    return withCors(json({ error: error.message || 'Không thể xuất danh mục.' }, 500), origin);
  }
}
