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
 * The browser currently uses only GET?action=check.
 * Mutation functions are already implemented here and will be wired to the
 * UI after the check endpoint is verified on the live GitHub Pages site.
 */

var REPO_OWNER = 'Zenkjt';
var REPO_NAME = 'tangthu-opds';
var REPO_BRANCH = 'main';
var CONFIG_PATH = 'config/branches.json';
var MUTATION_COOLDOWN_MS = 24 * 60 * 60 * 1000;

var DRIVE_SNAPSHOT_KEY = 'TANGTHU_DRIVE_SNAPSHOT_V1';
var DRIVE_SYNC_LOCK_MS = 30000;
var DRIVE_LIST_PAGE_SIZE = 1000;
var GITHUB_DISPATCH_EVENT = 'drive_changed';


/**
 * Tạo / thay thế trigger driveCheck mỗi 30 phút.
 *
 * Đồng thời tạo baseline snapshot hiện tại.
 * Từ đây trở đi driveCheck không dùng Drive Changes API nữa.
 */
function setupDriveChangeTrigger() {

  var lock = LockService.getScriptLock();
  lock.waitLock(DRIVE_SYNC_LOCK_MS);

  try {

    var triggers = ScriptApp.getProjectTriggers();

    for (var i = 0; i < triggers.length; i++) {

      if (
        triggers[i].getHandlerFunction() === 'driveCheck'
      ) {
        ScriptApp.deleteTrigger(triggers[i]);
      }
    }

    var config = readConfig_();

    var snapshot =
      buildDriveSnapshot_(config);

    saveDriveSnapshot_(snapshot);

    /*
     * Xóa checkpoint cũ của kiến trúc Drive Changes API
     * nếu nó còn tồn tại trong Script Properties.
     */
    PropertiesService
      .getScriptProperties()
      .deleteProperty(
        'TANGTHU_DRIVE_CHANGE_PAGE_TOKEN'
      );

    ScriptApp
      .newTrigger('driveCheck')
      .timeBased()
      .everyMinutes(30)
      .create();

    return {
      ok: true,
      trigger: 'driveCheck',
      interval_minutes: 30,
      branches: Object.keys(snapshot).length
    };

  } finally {

    lock.releaseLock();

  }
}


/**
 * Kiểm tra toàn bộ các tủ đã đăng ký.
 *
 * Cơ chế:
 *
 *   Google Drive files.list
 *          ↓
 *   fingerprint từng tủ
 *          ↓
 *   so với snapshot lần trước
 *          ↓
 *   khác → GitHub repository_dispatch
 *
 * Không dùng Drive Changes API.
 */
function driveCheck() {

  var lock = LockService.getScriptLock();

  if (
    !lock.tryLock(
      DRIVE_SYNC_LOCK_MS
    )
  ) {
    return {
      ok: false,
      skipped: true,
      reason: 'Một lần driveCheck khác đang chạy.'
    };
  }

  try {

    var config = readConfig_();

    var currentSnapshot =
      buildDriveSnapshot_(config);

    var previousSnapshot =
      loadDriveSnapshot_();

    /*
     * Lần đầu chưa có baseline:
     * chỉ lưu snapshot, không build.
     */
    if (!previousSnapshot) {

      saveDriveSnapshot_(
        currentSnapshot
      );

      return {
        ok: true,
        initialized: true,
        changed: false,
        branches:
          Object.keys(currentSnapshot).length
      };
    }


    /*
     * Chỉ so sánh những branch tồn tại ở cả hai snapshot.
     *
     * Branch mới / branch bị xóa / branch đổi tên:
     * đã được xử lý bởi writeConfig_() và GitHub push.
     *
     * Không dispatch thêm một build trùng.
     */
    var changedBranches =
      [];

    var currentIds =
      Object.keys(currentSnapshot);

    for (
      var i = 0;
      i < currentIds.length;
      i++
    ) {

      var branchId =
        currentIds[i];

      if (
        !previousSnapshot.hasOwnProperty(
          branchId
        )
      ) {
        continue;
      }

      if (
        currentSnapshot[branchId] !==
        previousSnapshot[branchId]
      ) {

        changedBranches.push(
          branchId
        );
      }
    }


    if (!changedBranches.length) {

      saveDriveSnapshot_(
        currentSnapshot
      );

      return {
        ok: true,
        changed: false,
        branches:
          currentIds.length
      };
    }


    /*
     * Có thay đổi thực sự trong nội dung / metadata
     * của ít nhất một tủ.
     */
    dispatchGitHubBuild_(
      changedBranches
    );

    /*
     * Chỉ cập nhật baseline sau khi GitHub dispatch
     * thành công. Nếu dispatch lỗi, lần chạy sau sẽ
     * thử lại.
     */
    saveDriveSnapshot_(
      currentSnapshot
    );

    return {
      ok: true,
      changed: true,
      dispatched: true,
      changed_branches:
        changedBranches,
      branches:
        currentIds.length
    };

  } finally {

    lock.releaseLock();

  }
}


/**
 * Tạo snapshot fingerprint cho tất cả branch đang
 * được bật.
 */
function buildDriveSnapshot_(config) {

  var apiKey =
    PropertiesService
      .getScriptProperties()
      .getProperty(
        'TANGTHU_GOOGLE_API_KEY'
      );

  if (!apiKey) {

    throw new Error(
      'Apps Script chưa được cấu hình TANGTHU_GOOGLE_API_KEY.'
    );
  }


  var snapshot = {};


  for (
    var i = 0;
    i < config.branches.length;
    i++
  ) {

    var branch =
      config.branches[i];

    if (!branch.enabled) {
      continue;
    }


    var scan =
      scanDriveBranch_(
        branch.root_folder_id,
        apiKey
      );


    if (!scan.ok) {

      throw new Error(
        'Không thể quét tủ "' +
        branch.display_name +
        '" (' +
        branch.root_folder_id +
        '): ' +
        scan.error
      );
    }


    snapshot[
      String(branch.id)
    ] =
      fingerprintDriveItems_(
        scan.items
      );
  }


  return snapshot;
}


/**
 * Quét đệ quy toàn bộ cây bên dưới một root folder.
 *
 * Không tải nội dung sách.
 * Chỉ lấy metadata:
 * id, parent, name, mimeType, size,
 * modifiedTime, createdTime, checksum.
 */
function scanDriveBranch_(
  rootFolderId,
  apiKey
) {

  var queue =
    [String(rootFolderId)];

  var visited = {};

  var items = [];


  while (queue.length) {

    var folderId =
      queue.shift();

    if (
      visited[folderId]
    ) {
      continue;
    }

    visited[folderId] = true;


    var result =
      listDriveFolder_(
        folderId,
        apiKey
      );


    if (!result.ok) {
      return result;
    }


    var files =
      result.files;


    for (
      var i = 0;
      i < files.length;
      i++
    ) {

      var file =
        files[i];


      items.push({

        id:
          String(file.id || ''),

        parent:
          folderId,

        name:
          String(file.name || ''),

        mime:
          String(file.mimeType || ''),

        size:
          String(
            file.size == null
              ? ''
              : file.size
          ),

        modified:
          String(
            file.modifiedTime || ''
          ),

        created:
          String(
            file.createdTime || ''
          ),

        checksum:
          String(
            file.md5Checksum || ''
          ),

        folder:
          file.mimeType ===
          'application/vnd.google-apps.folder'

      });


      if (
        file.mimeType ===
        'application/vnd.google-apps.folder'
      ) {

        queue.push(
          String(file.id)
        );
      }
    }
  }


  return {
    ok: true,
    items: items
  };
}


/**
 * files.list cho đúng một folder.
 *
 * Tàng Thư sử dụng API key vì các tủ sách MVP
 * là các folder Google Drive được chia sẻ công khai.
 */
function listDriveFolder_(
  folderId,
  apiKey
) {

  var allFiles = [];
  var pageToken = '';


  do {

    var url =
      'https://www.googleapis.com/drive/v3/files' +
      '?q=' +
      encodeURIComponent(
        "'" +
        folderId +
        "' in parents and trashed = false"
      ) +
      '&pageSize=' +
      DRIVE_LIST_PAGE_SIZE +
      '&supportsAllDrives=true' +
      '&includeItemsFromAllDrives=true' +
      '&fields=' +
      encodeURIComponent(
        'nextPageToken,' +
        'files(' +
          'id,' +
          'name,' +
          'mimeType,' +
          'size,' +
          'createdTime,' +
          'modifiedTime,' +
          'md5Checksum' +
        ')'
      ) +
      '&key=' +
      encodeURIComponent(apiKey);


    var response =
      UrlFetchApp.fetch(
        url,
        {
          method: 'get',
          muteHttpExceptions: true,
          headers: {
            Accept:
              'application/json'
          }
        }
      );


    var status =
      response.getResponseCode();

    var body =
      JSON.parse(
        response.getContentText() || '{}'
      );


    if (status !== 200) {

      return {
        ok: false,
        http_status: status,
        error:
          body.error &&
          body.error.message
            ? body.error.message
            : response.getContentText()
      };
    }


    var files =
      body.files || [];


    for (
      var i = 0;
      i < files.length;
      i++
    ) {

      allFiles.push(
        files[i]
      );
    }


    pageToken =
      body.nextPageToken
        ? String(
            body.nextPageToken
          )
        : '';

  } while (pageToken);


  return {
    ok: true,
    files: allFiles
  };
}


/**
 * Fingerprint ổn định cho toàn bộ cây.
 *
 * Bao gồm cả folder và file, nên các thay đổi:
 * - thêm
 * - xóa
 * - đổi tên
 * - sửa file
 * - di chuyển
 * - đổi MIME / size / checksum
 *
 * đều làm fingerprint thay đổi.
 */
function fingerprintDriveItems_(
  items
) {

  var rows = [];


  for (
    var i = 0;
    i < items.length;
    i++
  ) {

    var f =
      items[i];

    rows.push(
      [
        f.id,
        f.parent,
        f.folder ? 'D' : 'F',
        f.name,
        f.mime,
        f.size,
        f.created,
        f.modified,
        f.checksum
      ].join('\t')
    );
  }


  rows.sort();

  var canonical =
    rows.join('\n');


  var digest =
    Utilities.computeDigest(
      Utilities.DigestAlgorithm.SHA_256,
      canonical,
      Utilities.Charset.UTF_8
    );


  var hex = '';

  for (
    var j = 0;
    j < digest.length;
    j++
  ) {

    var value =
      digest[j];

    if (value < 0) {
      value += 256;
    }

    var h =
      value.toString(16);

    if (h.length < 2) {
      h = '0' + h;
    }

    hex += h;
  }


  return hex;
}


/**
 * Snapshot chỉ chứa fingerprint theo branch,
 * nên rất nhỏ và không chạm giới hạn 9 KB/value
 * của Apps Script Properties.
 */
function loadDriveSnapshot_() {

  var raw =
    PropertiesService
      .getScriptProperties()
      .getProperty(
        DRIVE_SNAPSHOT_KEY
      );


  if (!raw) {
    return null;
  }


  try {

    var value =
      JSON.parse(raw);

    if (
      !value ||
      typeof value !== 'object'
    ) {
      return null;
    }

    return value;

  } catch (err) {

    throw new Error(
      'Snapshot Drive bị hỏng: ' +
      String(err)
    );
  }
}


function saveDriveSnapshot_(
  snapshot
) {

  PropertiesService
    .getScriptProperties()
    .setProperty(
      DRIVE_SNAPSHOT_KEY,
      JSON.stringify(snapshot)
    );
}


/**
 * Gửi GitHub repository_dispatch.
 *
 * pageToken không còn dùng nữa; payload mới
 * chứa danh sách branch thay đổi.
 */
function dispatchGitHubBuild_(
  changedBranches
) {

  var token =
    githubToken_();


  var url =
    'https://api.github.com/repos/' +
    encodeURIComponent(
      REPO_OWNER
    ) +
    '/' +
    encodeURIComponent(
      REPO_NAME
    ) +
    '/dispatches';


  var payload = {

    event_type:
      GITHUB_DISPATCH_EVENT,

    client_payload: {

      source:
        'tangthu-apps-script',

      changed_branches:
        changedBranches,

      dispatched_at:
        new Date().toISOString()
    }
  };


  var response =
    UrlFetchApp.fetch(
      url,
      {
        method: 'post',
        muteHttpExceptions: true,
        contentType:
          'application/json',

        payload:
          JSON.stringify(
            payload
          ),

        headers:
          githubHeaders_(token)
      }
    );


  var status =
    response.getResponseCode();


  if (status !== 204) {

    throw new Error(
      'GitHub repository_dispatch thất bại: HTTP ' +
      status +
      ' ' +
      response.getContentText()
    );
  }
}


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
        next_mutation_at: new Date(now.getTime() + MUTATION_COOLDOWN_MS).toISOString()
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
        next_mutation_at: new Date(now.getTime() + MUTATION_COOLDOWN_MS).toISOString()
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
    throw new Error('GitHub ghi branches.json thất bại: HTTP ' + status +
      ' ' + response.getContentText());
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
