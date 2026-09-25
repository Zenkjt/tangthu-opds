/**
 * TÀNG THƯ — Apps Script control bridge
 *
 * Web App:
 *   Execute as: Me
 *   Who has access: Anyone
 *
 * Script Properties:
 *   TANGTHU_GOOGLE_API_KEY
 *   TANGTHU_GITHUB_TOKEN
 *
 * Drive change polling:
 *   Run setupDriveChangeTrigger() once manually.
 *   It creates a 30-minute time-driven trigger for driveCheck().
 *
 * Drive Changes API uses a persistent pageToken stored in
 * Script Properties. Apps Script only detects that Drive changed;
 * GitHub Actions remains responsible for rebuilding the catalog.
 */

var REPO_OWNER = 'Zenkjt';
var REPO_NAME = 'tangthu-opds';
var REPO_BRANCH = 'main';
var CONFIG_PATH = 'config/branches.json';

var MUTATION_COOLDOWN_MS = 24 * 60 * 60 * 1000;

var DRIVE_CHANGE_TOKEN_KEY = 'TANGTHU_DRIVE_CHANGE_PAGE_TOKEN';
var DRIVE_CHANGE_LOCK_KEY = 'TANGTHU_DRIVE_CHANGE_LOCK';

// -----------------------------------------------------------------------------
// Web app
// -----------------------------------------------------------------------------

function doGet(e) {
  var action = String((e && e.parameter && e.parameter.action) || '').trim().toLowerCase();

  if (action === 'check') {
    return jsonResponse(checkFolder_(String(e.parameter.drive || '')));
  }

  return jsonResponse({
    ok: false,
    error: 'Unsupported action'
  });
}

function doPost(e) {
  try {
    var body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    var action = String(body.action || '').trim().toLowerCase();

    if (action === 'create' || action === 'rename' || action === 'delete') {
      return jsonResponse(mutate_(action, body));
    }

    return jsonResponse({
      ok: false,
      error: 'Unsupported mutation'
    });
  } catch (err) {
    return jsonResponse({
      ok: false,
      error: String(err)
    });
  }
}

// -----------------------------------------------------------------------------
// Drive change trigger
// -----------------------------------------------------------------------------

/**
 * Run once manually from the Apps Script editor.
 * Existing TÀNG THƯ drive-check triggers are removed first.
 */
function setupDriveChangeTrigger() {
  var triggers = ScriptApp.getProjectTriggers();

  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'driveCheck') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }

  ScriptApp.newTrigger('driveCheck')
    .timeBased()
    .everyMinutes(30)
    .create();

  Logger.log('TÀNG THƯ: Drive change trigger installed (30 minutes).');
}

/**
 * Poll Google Drive Changes API.
 *
 * This function does NOT build the catalog and does NOT scan ebook files.
 * It only answers: "Has this Drive changed since the last checkpoint?"
 *
 * If yes, dispatch GitHub Actions. The checkpoint advances only after
 * the dispatch succeeds.
 *
 * The first run creates a baseline token and deliberately does not build.
 */
function driveCheck() {
  var lock = LockService.getScriptLock();

  if (!lock.tryLock(5000)) {
    Logger.log('TÀNG THƯ: driveCheck skipped because another check is running.');
    return;
  }

  try {
    var props = PropertiesService.getScriptProperties();
    var token = props.getProperty(DRIVE_CHANGE_TOKEN_KEY);

    if (!token) {
      var startToken = getDriveStartPageToken_();
      props.setProperty(DRIVE_CHANGE_TOKEN_KEY, startToken);
      Logger.log('TÀNG THƯ: Drive change baseline initialized.');
      return;
    }

    var result = listDriveChanges_(token);

    if (!result.ok) {
      throw new Error(result.error);
    }

    if (!result.changed) {
      if (result.new_start_page_token) {
        props.setProperty(
          DRIVE_CHANGE_TOKEN_KEY,
          result.new_start_page_token
        );
      }

      Logger.log('TÀNG THƯ: no Drive changes.');
      return;
    }

    // Do not advance the token until GitHub dispatch succeeds.
    dispatchCatalogBuild_();

    if (result.new_start_page_token) {
      props.setProperty(
        DRIVE_CHANGE_TOKEN_KEY,
        result.new_start_page_token
      );
    }

    Logger.log('TÀNG THƯ: Drive changed; GitHub Actions dispatched.');
  } finally {
    lock.releaseLock();
  }
}

function getDriveStartPageToken_() {
  var url =
    'https://www.googleapis.com/drive/v3/changes/startPageToken' +
    '?spaces=drive';

  var response = driveOAuthFetch_(url);
  var status = response.getResponseCode();
  var body = parseJson_(response);

  if (status !== 200 || !body.startPageToken) {
    throw new Error(
      'Drive startPageToken thất bại: HTTP ' + status +
      ' ' + JSON.stringify(body)
    );
  }

  return String(body.startPageToken);
}

function listDriveChanges_(pageToken) {
  var nextToken = String(pageToken);
  var changed = false;
  var newestStartToken = null;

  while (nextToken) {
    var url =
      'https://www.googleapis.com/drive/v3/changes' +
      '?pageToken=' + encodeURIComponent(nextToken) +
      '&spaces=drive' +
      '&restrictToMyDrive=true' +
      '&includeRemoved=true' +
      '&pageSize=1000' +
      '&fields=nextPageToken,newStartPageToken,changes(fileId,removed,file(id,name,mimeType,trashed,parents,modifiedTime))';

    var response = driveOAuthFetch_(url);
    var status = response.getResponseCode();
    var body = parseJson_(response);

    if (status !== 200) {
      return {
        ok: false,
        error:
          'Drive changes.list thất bại: HTTP ' + status +
          ' ' + JSON.stringify(body)
      };
    }

    var changes = body.changes || [];
    if (changes.length > 0) {
      changed = true;
    }

    if (body.newStartPageToken) {
      newestStartToken = String(body.newStartPageToken);
    }

    nextToken = body.nextPageToken
      ? String(body.nextPageToken)
      : null;
  }

  return {
    ok: true,
    changed: changed,
    new_start_page_token: newestStartToken
  };
}

function dispatchCatalogBuild_() {
  var token = githubToken_();

  // workflow_dispatch needs Actions: write permission on a fine-grained token.
  var url =
    'https://api.github.com/repos/' +
    encodeURIComponent(REPO_OWNER) + '/' +
    encodeURIComponent(REPO_NAME) +
    '/actions/workflows/cloudflare.yml/dispatches';

  var payload = {
    ref: REPO_BRANCH
  };

  var response = UrlFetchApp.fetch(url, {
    method: 'post',
    muteHttpExceptions: true,
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    headers: githubHeaders_(token)
  });

  var status = response.getResponseCode();

  if (status !== 204) {
    throw new Error(
      'GitHub Actions dispatch thất bại: HTTP ' + status +
      ' ' + response.getContentText()
    );
  }
}

function driveOAuthFetch_(url) {
  return UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: {
      Authorization: 'Bearer ' + ScriptApp.getOAuthToken(),
      Accept: 'application/json'
    }
  });
}

function parseJson_(response) {
  var text = response.getContentText() || '{}';

  try {
    return JSON.parse(text);
  } catch (err) {
    return {
      raw: text
    };
  }
}

// -----------------------------------------------------------------------------
// Shelf registry / mutation
// -----------------------------------------------------------------------------

function checkFolder_(driveUrl) {
  var folderId = parseDriveId_(driveUrl);
  if (!folderId) {
    return {
      ok: false,
      error: 'Không nhận ra Folder ID từ đường link Google Drive.'
    };
  }

  var folder = getDriveFolder_(folderId);
  if (!folder.ok) return folder;

  var config = readConfig_();
  var found = null;

  for (var i = 0; i < config.branches.length; i++) {
    if (String(config.branches[i].root_folder_id) === String(folderId)) {
      found = config.branches[i];
      break;
    }
  }

  var result = {
    ok: true,
    folder_id: folderId,
    folder_name: folder.name,
    registered: !!found
  };

  if (found) {
    result.shelf = found;
    result.next_mutation_at = nextMutationAt_(found.last_mutation);
    result.can_mutate = canMutate_(found.last_mutation);
  }

  return result;
}

function mutate_(action, body) {
  var folderId = parseDriveId_(String(body.drive_url || body.folder_id || ''));
  if (!folderId) {
    return {
      ok: false,
      error: 'Không nhận ra Folder ID từ đường link Google Drive.'
    };
  }

  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var folder = getDriveFolder_(folderId);
    if (!folder.ok) return folder;

    var config = readConfig_();
    var index = -1;

    for (var i = 0; i < config.branches.length; i++) {
      if (String(config.branches[i].root_folder_id) === String(folderId)) {
        index = i;
        break;
      }
    }

    var now = new Date();
    var nowIso = now.toISOString();

    if (action === 'create') {
      if (index >= 0) {
        return mutationBlocked_(config.branches[index], 'Tủ sách này đã được đăng ký.');
      }

      var displayName = String(body.display_name || '').trim();
      if (!displayName) {
        return {
          ok: false,
          error: 'Tên tủ sách không được để trống.'
        };
      }

      config.branches.push({
        id: 'g-' + Utilities.getUuid().replace(/-/g, '').slice(0, 12),
        display_name: displayName,
        root_folder_id: folderId,
        enabled: true,
        last_mutation: nowIso
      });

      writeConfig_(config, 'TÀNG THƯ: tạo tủ ' + displayName);

      return {
        ok: true,
        action: 'create',
        folder_id: folderId,
        folder_name: folder.name,
        display_name: displayName,
        next_mutation_at: nextMutationAt_(nowIso)
      };
    }

    if (index < 0) {
      return {
        ok: false,
        error: 'Tủ sách này chưa được đăng ký trong Tàng Thư.'
      };
    }

    var branch = config.branches[index];

    if (!canMutate_(branch.last_mutation)) {
      return mutationBlocked_(branch, 'Tủ này đang trong thời gian chờ 24 giờ.');
    }

    if (action === 'rename') {
      var newName = String(body.display_name || '').trim();
      if (!newName) {
        return {
          ok: false,
          error: 'Tên tủ sách không được để trống.'
        };
      }

      branch.display_name = newName;
      branch.last_mutation = nowIso;

      writeConfig_(config, 'TÀNG THƯ: đổi tên tủ ' + newName);

      return {
        ok: true,
        action: 'rename',
        folder_id: folderId,
        folder_name: folder.name,
        display_name: newName,
        next_mutation_at: nextMutationAt_(nowIso)
      };
    }

    if (action === 'delete') {
      config.branches.splice(index, 1);

      writeConfig_(config, 'TÀNG THƯ: xóa tủ ' + branch.display_name);

      return {
        ok: true,
        action: 'delete',
        folder_id: folderId,
        folder_name: folder.name,
        display_name: branch.display_name
      };
    }

    return {
      ok: false,
      error: 'Unsupported mutation'
    };
  } finally {
    lock.releaseLock();
  }
}

function getDriveFolder_(folderId) {
  var apiKey = PropertiesService.getScriptProperties()
    .getProperty('TANGTHU_GOOGLE_API_KEY');

  if (!apiKey) {
    return {
      ok: false,
      error: 'Apps Script chưa được cấu hình TANGTHU_GOOGLE_API_KEY.'
    };
  }

  var endpoint =
    'https://www.googleapis.com/drive/v3/files/' +
    encodeURIComponent(folderId) +
    '?fields=id,name,mimeType,trashed&supportsAllDrives=true&key=' +
    encodeURIComponent(apiKey);

  try {
    var response = UrlFetchApp.fetch(endpoint, {
      method: 'get',
      muteHttpExceptions: true,
      headers: { Accept: 'application/json' }
    });

    var status = response.getResponseCode();
    var body = JSON.parse(response.getContentText() || '{}');

    if (status !== 200) {
      return {
        ok: false,
        error: 'Không thể truy cập thư mục Google Drive.',
        folder_id: folderId,
        http_status: status
      };
    }

    if (body.trashed) {
      return {
        ok: false,
        error: 'Thư mục Google Drive này đã vào thùng rác.',
        folder_id: folderId
      };
    }

    if (body.mimeType !== 'application/vnd.google-apps.folder') {
      return {
        ok: false,
        error: 'Link không trỏ tới một thư mục Google Drive.',
        folder_id: folderId
      };
    }

    return {
      ok: true,
      id: body.id,
      name: body.name
    };
  } catch (err) {
    return {
      ok: false,
      error: 'Lỗi khi kiểm tra Google Drive: ' + String(err)
    };
  }
}

function readConfig_() {
  var token = githubToken_();
  var url = githubContentsUrl_();

  var response = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: githubHeaders_(token)
  });

  var status = response.getResponseCode();
  if (status !== 200) {
    throw new Error('GitHub đọc branches.json thất bại: HTTP ' + status);
  }

  var data = JSON.parse(response.getContentText());
  var raw = Utilities.newBlob(
    Utilities.base64Decode(String(data.content || '').replace(/\n/g, ''))
  ).getDataAsString('UTF-8');

  var config = JSON.parse(raw);
  if (!config.branches) config.branches = [];

  return {
    branches: config.branches,
    sha: data.sha
  };
}

function writeConfig_(config, message) {
  var token = githubToken_();
  var current = readConfig_();
  var content = JSON.stringify({branches: config.branches}, null, 2) + '\n';

  var payload = {
    message: message,
    content: Utilities.base64Encode(
      Utilities.newBlob(content).getBytes()
    ),
    sha: current.sha,
    branch: REPO_BRANCH
  };

  var response = UrlFetchApp.fetch(githubContentsUrl_(), {
    method: 'put',
    muteHttpExceptions: true,
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    headers: githubHeaders_(token)
  });

  var status = response.getResponseCode();
  if (status !== 200 && status !== 201) {
    throw new Error(
      'GitHub ghi branches.json thất bại: HTTP ' + status +
      ' ' + response.getContentText()
    );
  }
}

function githubToken_() {
  var token = PropertiesService.getScriptProperties()
    .getProperty('TANGTHU_GITHUB_TOKEN');

  if (!token) {
    throw new Error('Apps Script chưa được cấu hình TANGTHU_GITHUB_TOKEN.');
  }

  return token.trim();
}

function githubContentsUrl_() {
  return 'https://api.github.com/repos/' +
    encodeURIComponent(REPO_OWNER) + '/' +
    encodeURIComponent(REPO_NAME) + '/contents/' +
    CONFIG_PATH;
}

function githubHeaders_(token) {
  return {
    Accept: 'application/vnd.github+json',
    Authorization: 'Bearer ' + token,
    'X-GitHub-Api-Version': '2026-03-10'
  };
}

function canMutate_(lastMutation) {
  if (!lastMutation) return true;

  var t = new Date(lastMutation).getTime();
  if (isNaN(t)) return true;

  return Date.now() - t >= MUTATION_COOLDOWN_MS;
}

function nextMutationAt_(lastMutation) {
  if (!lastMutation) return null;

  var t = new Date(lastMutation).getTime();
  if (isNaN(t)) return null;

  return new Date(t + MUTATION_COOLDOWN_MS).toISOString();
}

function mutationBlocked_(branch, message) {
  return {
    ok: false,
    error: message,
    folder_id: branch.root_folder_id,
    display_name: branch.display_name,
    next_mutation_at: nextMutationAt_(branch.last_mutation),
    can_mutate: false
  };
}

function parseDriveId_(value) {
  var s = String(value || '').trim();

  var m = s.match(/\/drive\/(?:u\/\d+\/)?folders\/([A-Za-z0-9_-]+)/);
  if (m) return m[1];

  m = s.match(/\/folders\/([A-Za-z0-9_-]+)/);
  if (m) return m[1];

  m = s.match(/[?&]id=([A-Za-z0-9_-]+)/);
  if (m) return m[1];

  return '';
}

function jsonResponse(value) {
  return ContentService
    .createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}
