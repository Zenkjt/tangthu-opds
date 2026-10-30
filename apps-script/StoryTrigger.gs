/**
 * TÀNG THƯ — CrossPoint Story Trigger receptor
 *
 * CrossPoint sends only:
 *   { action: "story_trigger", shelf_no: 12, direction: "next"|"previous" }
 *
 * This bridge resolves shelf_no through config/branches.json and forwards
 * the resolved user_id/folder_id to the dedicated Story Worker trigger API.
 */

var STORY_TRIGGER_WORKER_URL_ =
  'https://tangthu-story-worker.mienluongnon.workers.dev/story/trigger';

function storyTrigger_(body) {
  var shelfNo = Number(body && body.shelf_no);
  var direction = String(body && body.direction || '').trim().toLowerCase();

  if (!Number.isInteger(shelfNo) || shelfNo < 1) {
    throw new Error('shelf_no không hợp lệ');
  }

  if (direction !== 'next' && direction !== 'previous') {
    throw new Error('direction không hợp lệ');
  }

  var branches = loadStoryTriggerBranches_();
  var branch = null;

  for (var i = 0; i < branches.length; i++) {
    var candidate = branches[i];
    if (Number(candidate.shelf_no) === shelfNo) {
      branch = candidate;
      break;
    }
  }

  if (!branch) {
    throw new Error('Không tìm thấy tủ #' + shelfNo);
  }

  if (branch.enabled === false) {
    throw new Error('Tủ #' + shelfNo + ' đang bị vô hiệu hóa');
  }

  var userId = String(branch.id || '').trim();
  var folderId = String(branch.root_folder_id || '').trim();

  if (!userId || !folderId) {
    throw new Error('Tủ #' + shelfNo + ' thiếu id hoặc root_folder_id');
  }

  var token = String(
    PropertiesService.getScriptProperties()
      .getProperty('STORY_TRIGGER_TOKEN') || ''
  ).trim();

  if (!token) {
    throw new Error('STORY_TRIGGER_TOKEN chưa được cấu hình');
  }

  var response = UrlFetchApp.fetch(STORY_TRIGGER_WORKER_URL_, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + token
    },
    payload: JSON.stringify({
      user_id: userId,
      folder_id: folderId,
      action: direction
    }),
    muteHttpExceptions: true
  });

  var status = response.getResponseCode();
  var text = response.getContentText();
  var result = null;

  try {
    result = JSON.parse(text || '{}');
  } catch (e) {
    result = { ok: false, error: 'Story Worker trả về dữ liệu không hợp lệ' };
  }

  if (status < 200 || status >= 300 || result.ok === false) {
    throw new Error(
      result.error || ('Story Worker HTTP ' + status)
    );
  }

  return {
    ok: true,
    status: 'queued',
    shelf_no: shelfNo,
    shelf_name: String(branch.display_name || ''),
    direction: direction,
    request_id: result.request_id || null
  };
}

function loadStoryTriggerBranches_() {
  var url =
    'https://raw.githubusercontent.com/' +
    REPO_OWNER + '/' + REPO_NAME +
    '/' + REPO_BRANCH + '/' + CONFIG_PATH;

  var response = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: {
      Accept: 'application/json'
    }
  });

  var status = response.getResponseCode();
  if (status < 200 || status >= 300) {
    throw new Error('Không đọc được branches.json: HTTP ' + status);
  }

  var data = JSON.parse(response.getContentText() || '{}');
  if (!data || !Array.isArray(data.branches)) {
    throw new Error('branches.json không hợp lệ');
  }

  return data.branches;
}
