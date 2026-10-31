/**
 * TÀNG THƯ — Apps Script control bridge
 *
 * Drive sync architecture V5:
 *   Google Drive Changes API
 *      -> cheap change detector
 *      -> no recursive folder scan
 *      -> one GitHub repository_dispatch per completed change backlog
 *
 * The detector does NOT fingerprint shelves and does NOT walk Drive trees.
 * The static catalog generator remains responsible for reading Drive content.
 *
 * Change logs:
 *   - My Drive user change log
 *   - One shared-drive change log per shared drive containing a registered shelf
 *
 * Checkpoints are advanced only after a GitHub dispatch succeeds.
 */

var REPO_OWNER = 'Zenkjt';
var REPO_NAME = 'tangthu-opds';
var REPO_BRANCH = 'main';
var CONFIG_PATH = 'config/branches.json';

var MUTATION_COOLDOWN_MS = 24 * 60 * 60 * 1000;

var DRIVE_CHANGE_STATE_KEY = 'TANGTHU_DRIVE_CHANGE_STATE_V5';
var DRIVE_SYNC_LOCK_MS = 30000;
var DRIVE_CHANGE_PAGE_SIZE = 1000;
var DRIVE_CHANGE_MAX_PAGES_PER_RUN = 20;
var DRIVE_CHANGE_TIME_BUDGET_MS = 4 * 60 * 1000;
var GITHUB_DISPATCH_EVENT = 'drive_changed';

var DRIVE_FOLDER_MIME = 'application/vnd.google-apps.folder';


function setupDriveChangeTrigger() {
  var lock = LockService.getScriptLock();
  lock.waitLock(DRIVE_SYNC_LOCK_MS);

  try {
    var triggers = ScriptApp.getProjectTriggers();

    for (var i = 0; i < triggers.length; i++) {
      if (triggers[i].getHandlerFunction() === 'driveCheck') {
        ScriptApp.deleteTrigger(triggers[i]);
      }
    }

    var config = readConfig_();
    var state = initializeDriveChangeState_(config);

    PropertiesService.getScriptProperties()
      .setProperty(DRIVE_CHANGE_STATE_KEY, JSON.stringify(state));

    ScriptApp.newTrigger('driveCheck')
      .timeBased()
      .everyMinutes(30)
      .create();

    Logger.log(
      'TÀNG THƯ: Drive Changes detector V5 initialized. ' +
      'shared_drives=' + Object.keys(state.shared || {}).length
    );

    return {
      ok: true,
      trigger: 'driveCheck',
      interval_minutes: 30,
      detector: 'changes_api_v5',
      shared_drives: Object.keys(state.shared || {}).length
    };
  } finally {
    lock.releaseLock();
  }
}


function driveCheck() {
  var startedAt = Date.now();
  var lock = LockService.getScriptLock();

  if (!lock.tryLock(DRIVE_SYNC_LOCK_MS)) {
    Logger.log('TÀNG THƯ: driveCheck skipped because another check is running.');
    return {
      ok: true,
      skipped: true,
      reason: 'Một lần driveCheck khác đang chạy.'
    };
  }

  try {
    var props = PropertiesService.getScriptProperties();
    var config = readConfig_();
    var state = loadDriveChangeState_();

    if (!state) {
      state = initializeDriveChangeState_(config);
      saveDriveChangeState_(state);

      Logger.log('TÀNG THƯ: Drive Changes baseline initialized.');
      return {
        ok: true,
        initialized: true,
        changed: false
      };
    }

    state = reconcileDriveChangeCorpora_(state, config);

    var order = state.order || [];
    if (!order.length) {
      saveDriveChangeState_(state);
      Logger.log('TÀNG THƯ: no Drive change corpora configured.');
      return {
        ok: true,
        changed: false,
        corpora: 0
      };
    }

    var pages = 0;

    while (
      state.cursor < order.length &&
      pages < DRIVE_CHANGE_MAX_PAGES_PER_RUN &&
      Date.now() - startedAt < DRIVE_CHANGE_TIME_BUDGET_MS
    ) {
      var corpusKey = order[state.cursor];
      var corpus = getCorpusState_(state, corpusKey);

      if (!corpus) {
        state.cursor++;
        continue;
      }

      var pageToken = corpus.pending_token || corpus.token;

      if (!pageToken) {
        pageToken = getCorpusStartPageToken_(corpus);
        corpus.token = pageToken;
        corpus.pending_token = '';
      }

      var result = listDriveChangesPage_(corpus, pageToken);
      pages++;

      if (!result.ok) {
        if (result.rebaseline) {
          corpus.token = getCorpusStartPageToken_(corpus);
          corpus.pending_token = '';
          state.changed = true;
          state.change_count = Number(state.change_count || 0) + 1;
          if (!state.changed_corpora) {
            state.changed_corpora = {};
          }
          state.changed_corpora[corpusKey] = true;
          state.cursor++;
          saveDriveChangeState_(state);

          Logger.log(
            'TÀNG THƯ: invalid Drive change token; corpus re-baselined. ' +
            'A build will be dispatched to reconcile current Drive state. ' +
            'corpus=' + corpusKey
          );
          continue;
        }

        throw new Error(result.error);
      }

      if (result.change_count > 0) {
        state.changed = true;
        state.change_count = Number(state.change_count || 0) + result.change_count;

        if (!state.changed_corpora) {
          state.changed_corpora = {};
        }
        state.changed_corpora[corpusKey] = true;
      }

      if (result.next_page_token) {
        corpus.pending_token = result.next_page_token;

        saveDriveChangeState_(state);

        Logger.log(
          'TÀNG THƯ: change backlog checkpoint. corpus=' +
          corpusKey +
          ' changes=' + result.change_count +
          ' next_page=yes'
        );

        return {
          ok: true,
          phase: 'changes',
          completed: false,
          changed: !!state.changed,
          pages: pages
        };
      }

      if (!result.new_start_page_token) {
        throw new Error(
          'Drive changes.list không trả về newStartPageToken.'
        );
      }

      corpus.token = result.new_start_page_token;
      corpus.pending_token = '';
      state.cursor++;

      saveDriveChangeState_(state);

      Logger.log(
        'TÀNG THƯ: change corpus complete. corpus=' +
        corpusKey +
        ' changes=' + result.change_count
      );
    }

    if (state.cursor < order.length) {
      saveDriveChangeState_(state);

      return {
        ok: true,
        phase: 'changes',
        completed: false,
        changed: !!state.changed,
        pages: pages,
        remaining_corpora: order.length - state.cursor
      };
    }

    if (!state.changed) {
      state.cursor = 0;
      state.change_count = 0;
      state.changed_corpora = {};
      saveDriveChangeState_(state);

      Logger.log('TÀNG THƯ: no Drive changes.');

      return {
        ok: true,
        changed: false,
        pages: pages
      };
    }

    /*
     * IMPORTANT:
     * Do not advance the durable checkpoints beyond this point until the
     * GitHub dispatch succeeds. If dispatch fails, the last saved checkpoint
     * remains available and the changes will be replayed safely.
     */
    dispatchGitHubBuild_({
      change_count: Number(state.change_count || 0),
      corpora: Object.keys(state.changed_corpora || {}),
      detected_at: new Date().toISOString()
    });

    state.cursor = 0;
    state.changed = false;
    state.change_count = 0;
    state.changed_corpora = {};

    saveDriveChangeState_(state);

    Logger.log(
      'TÀNG THƯ: Drive changes detected; GitHub Actions dispatched.'
    );

    return {
      ok: true,
      changed: true,
      dispatched: true,
      pages: pages
    };
  } finally {
    lock.releaseLock();
  }
}


function initializeDriveChangeState_(config) {
  var sharedDriveIds = discoverConfiguredSharedDrives_(config);
  var state = {
    version: 5,
    config_sha: String(config.sha || ''),
    order: ['user'],
    user: {
      type: 'user',
      drive_id: '',
      token: '',
      pending_token: ''
    },
    shared: {},
    cursor: 0,
    changed: false,
    change_count: 0,
    changed_corpora: {}
  };

  state.user.token = getCorpusStartPageToken_(state.user);

  for (var i = 0; i < sharedDriveIds.length; i++) {
    var driveId = sharedDriveIds[i];

    state.shared[driveId] = {
      type: 'shared',
      drive_id: driveId,
      token: '',
      pending_token: ''
    };

    state.shared[driveId].token =
      getCorpusStartPageToken_(state.shared[driveId]);

    state.order.push('drive:' + driveId);
  }

  return state;
}


function reconcileDriveChangeCorpora_(state, config) {
  if (Number(state.version || 0) !== 5) {
    return initializeDriveChangeState_(config);
  }

  var configuredDriveIds = discoverConfiguredSharedDrivesIfConfigChanged_(
    state,
    config
  );

  if (String(state.config_sha || '') === String(config.sha || '')) {
    return state;
  }

  /*
   * Keep all existing checkpoints. A config change must never discard an
   * already-consumed Drive change backlog.
   */
  var existing = state.shared || {};
  var nextShared = {};
  var nextOrder = ['user'];

  for (var i = 0; i < configuredDriveIds.length; i++) {
    var driveId = configuredDriveIds[i];

    if (existing[driveId]) {
      nextShared[driveId] = existing[driveId];
    } else {
      nextShared[driveId] = {
        type: 'shared',
        drive_id: driveId,
        token: getCorpusStartPageToken_({
          type: 'shared',
          drive_id: driveId
        }),
        pending_token: ''
      };
    }

    nextOrder.push('drive:' + driveId);
  }

  state.shared = nextShared;
  state.order = nextOrder;
  state.config_sha = String(config.sha || '');
  state.cursor = Math.min(
    Number(state.cursor || 0),
    Math.max(nextOrder.length - 1, 0)
  );

  return state;
}


function discoverConfiguredSharedDrivesIfConfigChanged_(state, config) {
  if (String(state.config_sha || '') === String(config.sha || '')) {
    var ids = [];
    var keys = Object.keys(state.shared || {});

    for (var i = 0; i < keys.length; i++) {
      ids.push(keys[i]);
    }

    return ids;
  }

  return discoverConfiguredSharedDrives_(config);
}


function discoverConfiguredSharedDrives_(config) {
  var ids = {};
  var apiKey = PropertiesService.getScriptProperties()
    .getProperty('TANGTHU_GOOGLE_API_KEY');

  if (!apiKey) {
    throw new Error(
      'Apps Script chưa được cấu hình TANGTHU_GOOGLE_API_KEY.'
    );
  }

  for (var i = 0; i < config.branches.length; i++) {
    var branch = config.branches[i];

    if (branch.enabled === false) {
      continue;
    }

    var rootId = String(branch.root_folder_id || '').trim();
    if (!rootId) {
      continue;
    }

    var corpus = getDriveCorpusForFolder_(rootId, apiKey);

    if (!corpus.ok) {
      throw new Error(
        'Không xác định được Drive corpus của tủ "' +
        String(branch.display_name || branch.id || rootId) +
        '": ' + corpus.error
      );
    }

    if (corpus.drive_id) {
      ids[corpus.drive_id] = true;
    }
  }

  return Object.keys(ids);
}


function getDriveCorpusForFolder_(folderId, apiKey) {
  var endpoint =
    'https://www.googleapis.com/drive/v3/files/' +
    encodeURIComponent(folderId) +
    '?fields=id,mimeType,trashed,driveId' +
    '&supportsAllDrives=true' +
    '&key=' + encodeURIComponent(apiKey);

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
        error:
          'Google Drive root lookup thất bại: HTTP ' +
          status + ' ' + response.getContentText()
      };
    }

    if (body.trashed) {
      return {
        ok: false,
        error: 'Tủ sách đang ở thùng rác.'
      };
    }

    if (body.mimeType !== DRIVE_FOLDER_MIME) {
      return {
        ok: false,
        error: 'root_folder_id không trỏ tới folder.'
      };
    }

    return {
      ok: true,
      drive_id: body.driveId ? String(body.driveId) : ''
    };
  } catch (err) {
    return {
      ok: false,
      error: String(err)
    };
  }
}


function getCorpusState_(state, corpusKey) {
  if (corpusKey === 'user') {
    return state.user;
  }

  if (corpusKey.indexOf('drive:') === 0) {
    return (state.shared || {})[corpusKey.slice(6)] || null;
  }

  return null;
}


function getCorpusStartPageToken_(corpus) {
  var url =
    'https://www.googleapis.com/drive/v3/changes/startPageToken' +
    '?supportsAllDrives=true';

  if (corpus.type === 'shared') {
    url += '&driveId=' + encodeURIComponent(corpus.drive_id);
  }

  var response = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: {
      Authorization: 'Bearer ' + ScriptApp.getOAuthToken(),
      Accept: 'application/json'
    }
  });

  var status = response.getResponseCode();
  var body = JSON.parse(response.getContentText() || '{}');

  if (status !== 200 || !body.startPageToken) {
    throw new Error(
      'Drive startPageToken thất bại: HTTP ' +
      status + ' ' + response.getContentText()
    );
  }

  return String(body.startPageToken);
}


function listDriveChangesPage_(corpus, pageToken) {
  var url =
    'https://www.googleapis.com/drive/v3/changes' +
    '?pageToken=' + encodeURIComponent(pageToken) +
    '&pageSize=' + DRIVE_CHANGE_PAGE_SIZE +
    '&includeRemoved=true' +
    '&supportsAllDrives=true' +
    '&spaces=drive' +
    '&fields=' +
    encodeURIComponent(
      'nextPageToken,newStartPageToken,changes(fileId,removed,file(id))'
    );

  if (corpus.type === 'user') {
    /*
     * The user log is restricted to the user's My Drive corpus.
     * Shared drives are tracked separately below.
     */
    url += '&restrictToMyDrive=true';
  } else {
    url +=
      '&driveId=' + encodeURIComponent(corpus.drive_id) +
      '&includeItemsFromAllDrives=true';
  }

  try {
    var response = UrlFetchApp.fetch(url, {
      method: 'get',
      muteHttpExceptions: true,
      headers: {
        Authorization: 'Bearer ' + ScriptApp.getOAuthToken(),
        Accept: 'application/json'
      }
    });

    var status = response.getResponseCode();
    var body = JSON.parse(response.getContentText() || '{}');

    if (status !== 200) {
      /*
       * An invalid/expired page token means we can no longer replay the
       * historical backlog. Re-baseline this corpus and force a build from
       * current Drive state rather than silently missing the change.
       */
      if (status === 400) {
        return {
          ok: false,
          rebaseline: true,
          error:
            'Drive changes.list trả HTTP 400. Page token không còn hợp lệ.'
        };
      }

      return {
        ok: false,
        error:
          'Drive changes.list thất bại: HTTP ' +
          status + ' ' + response.getContentText()
      };
    }

    return {
      ok: true,
      change_count: (body.changes || []).length,
      next_page_token: body.nextPageToken
        ? String(body.nextPageToken)
        : '',
      new_start_page_token: body.newStartPageToken
        ? String(body.newStartPageToken)
        : ''
    };
  } catch (err) {
    return {
      ok: false,
      error: String(err)
    };
  }
}


function loadDriveChangeState_() {
  var raw = PropertiesService.getScriptProperties()
    .getProperty(DRIVE_CHANGE_STATE_KEY);

  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(
      'Drive change state bị hỏng: ' + String(err)
    );
  }
}


function saveDriveChangeState_(state) {
  PropertiesService.getScriptProperties()
    .setProperty(
      DRIVE_CHANGE_STATE_KEY,
      JSON.stringify(state)
    );
}


function dispatchGitHubBuild_(info) {
  var token = githubToken_();

  var url =
    'https://api.github.com/repos/' +
    encodeURIComponent(REPO_OWNER) +
    '/' +
    encodeURIComponent(REPO_NAME) +
    '/dispatches';

  var payload = {
    event_type: GITHUB_DISPATCH_EVENT,
    client_payload: {
      source: 'tangthu-apps-script',
      change_count: Number(info.change_count || 0),
      corpora: info.corpora || [],
      detected_at: String(
        info.detected_at || new Date().toISOString()
      )
    }
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
      'GitHub repository_dispatch thất bại: HTTP ' +
      status + ' ' + response.getContentText()
    );
  }
}


function doGet(e) {

  var action = String((e && e.parameter && e.parameter.action) || '').trim().toLowerCase();



  if (action === 'check') {

    return jsonResponse(checkFolder_(String(e.parameter.drive || '')));

  }

  if (action === 'story_catalog') {
    return jsonResponse(
      storyCatalog_(String(e.parameter.shelf_no || ''))
    );
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
    if (action === 'upload_epub') {
      return jsonResponse(uploadEpub_(body));
    }
    if (action === 'story_cache') {
      return jsonResponse(storyCache_(body));
    }

    if (action === 'story_trigger') return jsonResponse(storyTrigger_(body));
    if (action === 'story_download') return jsonResponse(storyDownload_(body));

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
/**
 * Phase 10 — Google Drive EPUB upload action.
 *
 * Add this allowlist constant near the top of the existing Code.gs:
 *
 * var NEWS_UPLOAD_FOLDER_ID = '1hR0H-wZejPM59ka-340atSlJCCYaaUbs';
 * var NEWS_UPLOAD_ALLOWED_FILENAME = '0neNews.epub';
 *
 * Add the action branch to the EXISTING doPost(e) action router, before
 * "return jsonResponse({ ok:false, error:'Unsupported mutation' })":
 *
 * if (action === 'upload_epub') {
 *   return jsonResponse(uploadEpub_(body));
 * }
 *
 * Then append the helper below. Do not replace the rest of Code.gs.
 */

/**
 * Story + News EPUB upload endpoint.
 * Writes only to enabled registered shelves and allows only approved EPUB names.
 */
function uploadEpub_(body) {
  var props = PropertiesService.getScriptProperties();
  var expectedToken = String(props.getProperty('TANGTHU_UPLOAD_TOKEN') || '');
  var suppliedToken = String(body.token || '');
  if (!expectedToken || suppliedToken !== expectedToken) {
    return { ok: false, error: 'Unauthorized upload request.' };
  }

  var folderId = String(body.folder_id || '').trim();
  if (!folderId) return { ok: false, error: 'Missing target folder.' };

  var config = readConfig_();
  var registered = null;
  for (var i = 0; i < config.branches.length; i++) {
    var branch = config.branches[i];
    if (String(branch.root_folder_id) === folderId && branch.enabled !== false) {
      registered = branch;
      break;
    }
  }
  if (!registered) {
    return { ok: false, error: 'Target folder is not an active registered Tàng Thư shelf.' };
  }

  var filename = String(body.filename || '');
  var allowed = {
    '0neNews.epub': true,
    '0neStory.epub': true,
    '0neStoryTOC.epub': true
  };
  if (!allowed[filename]) return { ok: false, error: 'Filename is not allowlisted.' };
  if (String(body.mime_type || '') !== 'application/epub+zip') {
    return { ok: false, error: 'Unexpected MIME type.' };
  }

  var encoded = String(body.content_base64 || '');
  if (!encoded || encoded.length > 45 * 1024 * 1024) {
    return { ok: false, error: 'Missing or oversized EPUB payload.' };
  }

  var bytes;
  try {
    bytes = Utilities.base64Decode(encoded);
  } catch (err) {
    return { ok: false, error: 'Invalid base64 payload.' };
  }
  if (!bytes.length) return { ok: false, error: 'Empty EPUB payload.' };

  var folder;
  try {
    folder = DriveApp.getFolderById(folderId);
  } catch (err) {
    return {
      ok: false,
      error: 'Apps Script cannot write to this shelf. Check Editor/write permission: ' + String(err)
    };
  }

  var blob = Utilities.newBlob(bytes, 'application/epub+zip', filename);
  var matches = folder.getFilesByName(filename);
  if (matches.hasNext()) {
    var file = matches.next();
    if (matches.hasNext()) {
      return {
        ok: false,
        error: 'Multiple files named ' + filename + ' exist in target folder; refusing ambiguous overwrite.'
      };
    }
    try {
      Drive.Files.update(
        { name: filename, mimeType: 'application/epub+zip' },
        file.getId(),
        blob,
        { supportsAllDrives: true }
      );
      file = DriveApp.getFileById(file.getId());
      return {
        ok: true, operation: 'updated', filename: file.getName(),
        file_id: file.getId(), size: file.getSize(),
        shelf_id: registered.id, shelf_name: registered.display_name
      };
    } catch (err) {
      return {
        ok: false,
        error: 'Failed to update EPUB. Check Editor/write permission and Advanced Drive service: ' + String(err)
      };
    }
  }

  try {
    var created = Drive.Files.create(
      { name: filename, mimeType: 'application/epub+zip', parents: [folderId] },
      blob,
      { supportsAllDrives: true }
    );
    return {
      ok: true, operation: 'created', filename: created.name,
      file_id: created.id, size: bytes.length,
      shelf_id: registered.id, shelf_name: registered.display_name
    };
  } catch (err) {
    return {
      ok: false,
      error: 'Failed to create EPUB. Check Editor/write permission and Advanced Drive service: ' + String(err)
    };
  }
}


/**
 * Native CrossPoint Story catalog.
 *
 * The catalog itself is deliberately tiny: it only exposes PREVIOUS/NEXT.
 * The selected item is later expanded into the story_download POST body.
 */
function storyCatalog_(shelfNoRaw) {
  var shelfNo = Number(shelfNoRaw);

  if (!isFinite(shelfNo) || shelfNo <= 0 || Math.floor(shelfNo) !== shelfNo) {
    return {
      ok: false,
      error: 'Invalid shelf_no.'
    };
  }

  var config = readConfig_();
  var branch = findShelfByNo_(config.branches, shelfNo);

  if (!branch) {
    return {
      ok: false,
      error: 'Shelf #' + shelfNo + ' is not registered.'
    };
  }

  if (branch.enabled === false) {
    return {
      ok: false,
      error: 'Shelf #' + shelfNo + ' is disabled.'
    };
  }

  return {
    items: [
      {
        id: 'previous',
        title: 'PREVIOUS'
      },
      {
        id: 'next',
        title: 'NEXT'
      }
    ]
  };
}

/**
 * CrossPoint native Story download bridge.
 *
 * Flow:
 *   CrossPoint POST story_download
 *     -> trigger Story
 *     -> wait until the shelf's 0neStory.epub is created/updated
 *     -> return a JSON object containing the stable direct-download URL.
 *
 * CrossPoint's native device.json uses download.url_path = "url", so the
 * response itself is only the small JSON hand-off; the EPUB is fetched by
 * CrossPoint in the second HTTP request.
 *
 * Required branch shape:
 *   shelf_no: stable numeric shelf number
 *   root_folder_id: shelf root
 *   enabled: optional, defaults to enabled
 *
 * Existing storyTrigger_() remains the single Story trigger receptor.
 */
var STORY_DOWNLOAD_FILENAME = '0neStory.epub';
var STORY_DOWNLOAD_MAX_WAIT_MS = 180000;
var STORY_DOWNLOAD_POLL_MS = 3000;

function storyDownload_(body) {
  var shelfNo = Number(body.shelf_no);
  var direction = String(body.direction || '').trim().toLowerCase();

  if (!isFinite(shelfNo) || shelfNo <= 0 || Math.floor(shelfNo) !== shelfNo) {
    return {
      ok: false,
      error: 'Invalid shelf_no.'
    };
  }

  if (direction !== 'next' && direction !== 'previous') {
    return {
      ok: false,
      error: 'Invalid Story direction.'
    };
  }

  try {
    var config = readConfig_();
    var branch = findShelfByNo_(config.branches, shelfNo);

    if (!branch) {
      return {
        ok: false,
        error: 'Shelf #' + shelfNo + ' is not registered.'
      };
    }

    if (branch.enabled === false) {
      return {
        ok: false,
        error: 'Shelf #' + shelfNo + ' is disabled.'
      };
    }

    var folderId = String(branch.root_folder_id || '').trim();
    if (!folderId) {
      return {
        ok: false,
        error: 'Shelf #' + shelfNo + ' has no root_folder_id.'
      };
    }

    var before = findStoryEpub_(folderId);

    var triggerResult = storyTrigger_({
      action: 'story_trigger',
      shelf_no: shelfNo,
      direction: direction
    });

    if (!triggerResult || triggerResult.ok === false) {
      return {
        ok: false,
        error:
          'Story trigger failed: ' +
          String((triggerResult && triggerResult.error) || 'unknown error')
      };
    }

    var startedAt = Date.now();

    while (Date.now() - startedAt < STORY_DOWNLOAD_MAX_WAIT_MS) {
      Utilities.sleep(STORY_DOWNLOAD_POLL_MS);

      var current = findStoryEpub_(folderId);

      if (!current) {
        continue;
      }

      if (!before) {
        return storyDownloadResponse_(current, shelfNo, direction);
      }

      if (current.id !== before.id) {
        return storyDownloadResponse_(current, shelfNo, direction);
      }

      if (current.modifiedMs > before.modifiedMs) {
        return storyDownloadResponse_(current, shelfNo, direction);
      }
    }

    return {
      ok: false,
      error:
        'Story trigger completed but 0neStory.epub was not updated within ' +
        Math.round(STORY_DOWNLOAD_MAX_WAIT_MS / 1000) +
        ' seconds.'
    };
  }
}

function findShelfByNo_(branches, shelfNo) {
  var list = branches || [];

  for (var i = 0; i < list.length; i++) {
    var branch = list[i];

    if (
      branch &&
      Number(branch.shelf_no) === Number(shelfNo)
    ) {
      return branch;
    }
  }

  /*
   * Compatibility fallback for an older branches.json that has not yet
   * persisted shelf_no. This fallback is intentionally positional only.
   * Once shelf_no exists, it always wins.
   */
  if (shelfNo >= 1 && shelfNo <= list.length) {
    var fallback = list[shelfNo - 1];
    if (fallback) return fallback;
  }

  return null;
}

function findStoryEpub_(folderId) {
  var folder = DriveApp.getFolderById(folderId);
  var files = folder.getFilesByName(STORY_DOWNLOAD_FILENAME);

  if (!files.hasNext()) {
    return null;
  }

  var file = files.next();

  if (files.hasNext()) {
    throw new Error(
      'Multiple files named ' +
      STORY_DOWNLOAD_FILENAME +
      ' exist in shelf ' +
      folderId +
      '.'
    );
  }

  return {
    id: String(file.getId()),
    name: file.getName(),
    size: Number(file.getSize() || 0),
    modifiedMs: file.getLastUpdated().getTime()
  };
}

function storyDownloadResponse_(file, shelfNo, direction) {
  return {
    ok: true,
    action: 'story_download',
    shelf_no: shelfNo,
    direction: direction,
    filename: STORY_DOWNLOAD_FILENAME,
    file_id: file.id,
    size: file.size,
    modified_at: new Date(file.modifiedMs).toISOString(),

    /*
     * Stable URL: the Drive file ID is stable because Story upload updates
     * the existing 0neStory.epub rather than creating a new file.
     */
    url:
      'https://drive.usercontent.google.com/download?export=download&confirm=t&id=' +
      encodeURIComponent(file.id)
  };
}
