/**
 * TÀNG THƯ — Apps Script control bridge
 *
 * Drive sync:
 *   quick metadata scan
 *      -> item_count + total_size + max_modified_time
 *      -> unchanged: skip
 *      -> changed: full fingerprint scan
 *      -> confirmed change: GitHub repository_dispatch
 *
 * Full scans are checkpointed so no execution needs to run for 10 minutes.
 * Does not use Google Drive Changes API.
 */

var REPO_OWNER = 'Zenkjt';
var REPO_NAME = 'tangthu-opds';
var REPO_BRANCH = 'main';
var CONFIG_PATH = 'config/branches.json';

var MUTATION_COOLDOWN_MS = 24 * 60 * 60 * 1000;

var DRIVE_BRANCH_STATE_KEY = 'TANGTHU_DRIVE_BRANCH_STATE_V4';
var DRIVE_SCAN_STATE_KEY = 'TANGTHU_DRIVE_SCAN_STATE_V4';

var DRIVE_SYNC_LOCK_MS = 30000;
var DRIVE_LIST_PAGE_SIZE = 1000;
var DRIVE_TIME_BUDGET_MS = 4 * 60 * 1000;
var DRIVE_BRANCH_BUDGET_MS = 45 * 1000;
var GITHUB_DISPATCH_EVENT = 'drive_changed';


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

    var props = PropertiesService.getScriptProperties();

    props.deleteProperty(DRIVE_BRANCH_STATE_KEY);
    props.deleteProperty(DRIVE_SCAN_STATE_KEY);

    props.deleteProperty('TANGTHU_DRIVE_QUICK_SNAPSHOT_V3');
    props.deleteProperty('TANGTHU_DRIVE_FULL_SNAPSHOT_V3');
    props.deleteProperty('TANGTHU_DRIVE_SNAPSHOT_V1');
    props.deleteProperty('TANGTHU_DRIVE_CHANGE_PAGE_TOKEN');
    props.deleteProperty('TANGTHU_DRIVE_CHANGE_PROGRESS_TOKEN');
    props.deleteProperty('TANGTHU_DRIVE_CHANGE_PENDING');
    props.deleteProperty('TANGTHU_DRIVE_CHANGE_LOCK');

    ScriptApp.newTrigger('driveCheck')
      .timeBased()
      .everyMinutes(30)
      .create();

    Logger.log('TÀNG THƯ: driveCheck trigger created.');

    return {
      ok: true,
      trigger: 'driveCheck',
      interval_minutes: 30
    };
  } finally {
    lock.releaseLock();
  }
}


/*
 * One driveCheck execution does two jobs in the same round:
 *   1. continue baseline for shelves not yet baselined;
 *   2. re-check shelves that already have a baseline.
 *
 * Every shelf has its own durable quick signature and baseline_complete flag.
 * The cursor only decides which shelf gets attention next; it is not the
 * baseline itself. A timeout therefore cannot make completed shelves vanish.
 */
function driveCheck() {
  var startedAt = Date.now();
  var lock = LockService.getScriptLock();

  if (!lock.tryLock(DRIVE_SYNC_LOCK_MS)) {
    return {
      ok: false,
      skipped: true,
      reason: 'Một lần driveCheck khác đang chạy.'
    };
  }

  try {
    var config = readConfig_();
    var branchState = loadBranchState_();
    var scanState = loadScanState_();

    if (scanState && scanState.phase === 'full') {
      var fullResult = continueFullScan_(config, scanState, startedAt);
      if (fullResult.completed) {
        saveScanState_(null);
      }
      return fullResult;
    }

    var enabled = [];
    for (var i = 0; i < config.branches.length; i++) {
      if (config.branches[i].enabled) {
        enabled.push(config.branches[i]);
      }
    }

    if (!enabled.length) {
      saveBranchState_({ version: 4, cursor: 0, branches: {} });
      Logger.log('TÀNG THƯ: no enabled shelves.');
      return { ok: true, changed: false, baseline_complete: true };
    }

    branchState = normalizeBranchState_(branchState, enabled);

    Logger.log(
      'TÀNG THƯ: quick round START cursor=' + branchState.cursor +
      ' shelves=' + enabled.length +
      ' baseline=' + countBaselinedBranches_(branchState, enabled) + '/' + enabled.length
    );
    pruneFullSnapshot_(enabled);

    var processed = 0;
    var baselineCompletedThisRun = [];
    var changedBranches = [];

    while (Date.now() - startedAt < DRIVE_TIME_BUDGET_MS) {
      var index = Number(branchState.cursor || 0) % enabled.length;
      var branch = enabled[index];
      var id = String(branch.id);
      var entry = branchState.branches[id];

      var result = scanBranchQuick_(
        branch,
        entry,
        startedAt,
        branchState
      );

      if (!result.completed) {
        // This shelf has its own durable queue/checkpoint. Do not let a large
        // shelf monopolize the whole baseline round: move the cursor forward
        // and give the next shelf a chance in the same execution if time remains.
        branchState.cursor = (index + 1) % enabled.length;
        processed++;
        saveBranchState_(branchState);
        Logger.log(
          'TÀNG THƯ: branch CHECKPOINT branch=' + id +
          ' baseline=' + (entry.baseline_complete ? 'complete' : 'pending') +
          ' next_cursor=' + branchState.cursor +
          ' queue=' + (entry.scan_queue ? entry.scan_queue.length : 0) +
          ' files_so_far=' + Number(entry.item_count_work || 0) +
          ' elapsed=' + (Date.now() - startedAt) + 'ms'
        );
        continue;
      }

      entry.item_count = result.signature.item_count;
      entry.total_size = result.signature.total_size;
      entry.max_modified_time = result.signature.max_modified_time;
      entry.scan_queue = null;
      entry.visited = {};
      entry.item_count_work = 0;
      entry.total_size_work = 0;
      entry.max_modified_work = '';

      if (!entry.baseline_complete) {
        entry.baseline_complete = true;
        baselineCompletedThisRun.push(id);
      } else if (
        entry.item_count !== result.previous.item_count ||
        entry.total_size !== result.previous.total_size ||
        entry.max_modified_time !== result.previous.max_modified_time
      ) {
        changedBranches.push(id);
      }

      branchState.cursor = (index + 1) % enabled.length;
      processed++;

      Logger.log(
        'TÀNG THƯ: branch COMPLETE branch=' + id +
        ' baseline=' + (entry.baseline_complete ? 'complete' : 'newly-complete') +
        ' files=' + entry.item_count +
        ' next_cursor=' + branchState.cursor +
        ' elapsed=' + (Date.now() - startedAt) + 'ms'
      );

      if (changedBranches.length) {
        var fullState = {
          phase: 'full',
          branch_ids: changedBranches.slice(),
          branch_index: 0,
          folder_queue: null,
          visited: {},
          items: [],
          baseline_ids: []
        };
        saveBranchState_(branchState);
        saveScanState_(fullState);
        return continueFullScan_(config, fullState, startedAt);
      }
    }

    saveBranchState_(branchState);

    var allBaseline = allBranchesBaselined_(branchState, enabled);

    Logger.log(
      'TÀNG THƯ: quick round END processed=' + processed +
      ' cursor=' + branchState.cursor +
      ' baseline_complete=' + allBaseline +
      ' baselined=' + countBaselinedBranches_(branchState, enabled) + '/' + enabled.length +
      ' elapsed=' + (Date.now() - startedAt) + 'ms'
    );

    return {
      ok: true,
      phase: 'quick',
      completed: false,
      processed: processed,
      baseline_complete: allBaseline,
      baseline_completed_this_run: baselineCompletedThisRun
    };
  } finally {
    lock.releaseLock();
  }
}


/*
 * Scan one shelf. During the first baseline this establishes its signature.
 * On later rounds it compares the new signature against that shelf's stored
 * signature. The work itself is checkpointed at folder level.
 */
function scanBranchQuick_(branch, entry, startedAt, branchState) {
  var apiKey = PropertiesService.getScriptProperties()
    .getProperty('TANGTHU_GOOGLE_API_KEY');

  if (!apiKey) {
    throw new Error(
      'Apps Script chưa được cấu hình TANGTHU_GOOGLE_API_KEY.'
    );
  }

  var previous = {
    item_count: Number(entry.item_count || 0),
    total_size: Number(entry.total_size || 0),
    max_modified_time: String(entry.max_modified_time || '')
  };

  var queue = entry.scan_queue;
  var visited = entry.visited || {};
  var itemCount = Number(entry.item_count_work || 0);
  var totalSize = Number(entry.total_size_work || 0);
  var maxModified = String(entry.max_modified_work || '');

  if (!queue) {
    queue = [String(branch.root_folder_id)];
    visited = {};
    itemCount = 0;
    totalSize = 0;
    maxModified = '';
  }

  var branchStartedAt = Date.now();

  while (queue.length) {
    if (
      Date.now() - startedAt >= DRIVE_TIME_BUDGET_MS ||
      Date.now() - branchStartedAt >= DRIVE_BRANCH_BUDGET_MS
    ) {
      entry.scan_queue = queue;
      entry.visited = visited;
      entry.item_count_work = itemCount;
      entry.total_size_work = totalSize;
      entry.max_modified_work = maxModified;
      return {
        completed: false,
        previous: previous
      };
    }

    var folderId = queue.shift();

    if (visited[folderId]) {
      continue;
    }

    visited[folderId] = true;

    var result = listDriveFolder_(folderId, apiKey);

    if (!result.ok) {
      throw new Error(
        'Google Drive quick scan thất bại: ' + result.error
      );
    }

    var files = result.files || [];

    for (var i = 0; i < files.length; i++) {
      var file = files[i];
      itemCount++;

      if (file.size != null && file.size !== '') {
        totalSize += Number(file.size) || 0;
      }

      var modified = String(file.modifiedTime || '');
      if (modified > maxModified) {
        maxModified = modified;
      }

      if (
        file.mimeType ===
        'application/vnd.google-apps.folder'
      ) {
        queue.push(String(file.id));
      }
    }
  }

  return {
    completed: true,
    previous: previous,
    signature: {
      item_count: itemCount,
      total_size: totalSize,
      max_modified_time: maxModified
    }
  };
}


function continueFullScan_(config, state, startedAt) {
  var apiKey = PropertiesService.getScriptProperties()
    .getProperty('TANGTHU_GOOGLE_API_KEY');

  if (!apiKey) {
    throw new Error(
      'Apps Script chưa được cấu hình TANGTHU_GOOGLE_API_KEY.'
    );
  }

  var fullSnapshot = loadFullSnapshot_() || {};

  while (state.branch_index < state.branch_ids.length) {
    var branchId = String(state.branch_ids[state.branch_index]);
    var branch = findBranchById_(config, branchId);

    if (!branch) {
      state.branch_index++;
      state.folder_queue = null;
      state.visited = {};
      state.items = [];
      continue;
    }

    if (!state.folder_queue) {
      state.folder_queue = [String(branch.root_folder_id)];
      state.visited = {};
      state.items = [];
    }

    while (state.folder_queue.length) {
      if (Date.now() - startedAt >= DRIVE_TIME_BUDGET_MS) {
        saveScanState_(state);
        Logger.log(
          'TÀNG THƯ: full scan checkpoint. branch_index=' +
          state.branch_index
        );
        return {
          ok: true,
          phase: 'full',
          completed: false
        };
      }

      var folderId = state.folder_queue.shift();

      if (state.visited[folderId]) {
        continue;
      }

      state.visited[folderId] = true;

      var result = listDriveFolder_(folderId, apiKey);

      if (!result.ok) {
        throw new Error(
          'Google Drive full scan thất bại: ' + result.error
        );
      }

      var files = result.files || [];

      for (var i = 0; i < files.length; i++) {
        var file = files[i];

        state.items.push({
          id: String(file.id || ''),
          parent: folderId,
          name: String(file.name || ''),
          mime: String(file.mimeType || ''),
          size: file.size == null ? '' : String(file.size),
          modified: String(file.modifiedTime || ''),
          created: String(file.createdTime || ''),
          checksum: String(file.md5Checksum || ''),
          folder:
            file.mimeType ===
            'application/vnd.google-apps.folder'
        });

        if (
          file.mimeType ===
          'application/vnd.google-apps.folder'
        ) {
          state.folder_queue.push(String(file.id));
        }
      }
    }

    fullSnapshot[branchId] =
      fingerprintDriveItems_(state.items);

    state.branch_index++;
    state.folder_queue = null;
    state.visited = {};
    state.items = [];
  }

  var previousFull = loadFullSnapshot_() || {};
  var actuallyChanged = [];

  for (var j = 0; j < state.branch_ids.length; j++) {
    var id = String(state.branch_ids[j]);

    /*
     * The quick signature already proved that this shelf changed. If a
     * previous full fingerprint exists, require it to differ as well. For a
     * shelf's first change, there is no old fingerprint yet, so the changed
     * quick signature is the authoritative signal and we dispatch once.
     */
    if (
      !previousFull[id] ||
      fullSnapshot[id] !== previousFull[id]
    ) {
      actuallyChanged.push(id);
    }
  }

  saveFullSnapshot_(fullSnapshot);
  saveScanState_(null);

  if (actuallyChanged.length) {
    dispatchGitHubBuild_(actuallyChanged);

    Logger.log(
      'TÀNG THƯ: Drive changed; GitHub Actions dispatched. branches=' +
      JSON.stringify(actuallyChanged)
    );

    return {
      ok: true,
      phase: 'full',
      completed: true,
      changed: true,
      dispatched: true,
      changed_branches: actuallyChanged
    };
  }

  Logger.log(
    'TÀNG THƯ: full scan completed; no confirmed Drive changes.'
  );

  return {
    ok: true,
    phase: 'full',
    completed: true,
    changed: false
  };
}


function findBranchById_(config, id) {
  for (var i = 0; i < config.branches.length; i++) {
    if (String(config.branches[i].id) === String(id)) {
      return config.branches[i];
    }
  }
  return null;
}


function normalizeBranchState_(state, enabled) {
  if (!state || typeof state !== 'object') {
    state = { version: 4, cursor: 0, branches: {} };
  }

  if (!state.branches || typeof state.branches !== 'object') {
    state.branches = {};
  }

  for (var i = 0; i < enabled.length; i++) {
    var id = String(enabled[i].id);
    if (!state.branches[id]) {
      state.branches[id] = {
        baseline_complete: false,
        item_count: 0,
        total_size: 0,
        max_modified_time: '',
        scan_queue: null,
        visited: {},
        item_count_work: 0,
        total_size_work: 0,
        max_modified_work: ''
      };
    }
  }

  var valid = {};
  for (var j = 0; j < enabled.length; j++) {
    valid[String(enabled[j].id)] = true;
  }

  var keys = Object.keys(state.branches);
  for (var k = 0; k < keys.length; k++) {
    if (!valid[keys[k]]) {
      delete state.branches[keys[k]];
    }
  }

  state.version = 4;
  state.cursor = Number(state.cursor || 0) % Math.max(enabled.length, 1);

  return state;
}


function countBaselinedBranches_(branchState, enabled) {
  var count = 0;
  for (var i = 0; i < enabled.length; i++) {
    var id = String(enabled[i].id);
    var entry = branchState.branches[id];
    if (entry && entry.baseline_complete) {
      count++;
    }
  }
  return count;
}


function allBranchesBaselined_(state, enabled) {
  for (var i = 0; i < enabled.length; i++) {
    var entry = state.branches[String(enabled[i].id)];
    if (!entry || !entry.baseline_complete) {
      return false;
    }
  }
  return true;
}


function loadBranchState_() {
  var raw = PropertiesService.getScriptProperties()
    .getProperty(DRIVE_BRANCH_STATE_KEY);

  if (!raw) {
    return { version: 4, cursor: 0, branches: {} };
  }

  try {
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(
      'Drive branch state bị hỏng: ' + String(err)
    );
  }
}


function saveBranchState_(state) {
  PropertiesService.getScriptProperties()
    .setProperty(
      DRIVE_BRANCH_STATE_KEY,
      JSON.stringify(state)
    );
}


function pruneFullSnapshot_(enabled) {
  var snapshot = loadFullSnapshot_() || {};
  var valid = {};

  for (var i = 0; i < enabled.length; i++) {
    valid[String(enabled[i].id)] = true;
  }

  var keys = Object.keys(snapshot);
  var changed = false;
  for (var j = 0; j < keys.length; j++) {
    if (!valid[keys[j]]) {
      delete snapshot[keys[j]];
      changed = true;
    }
  }

  if (changed) {
    saveFullSnapshot_(snapshot);
  }
}


function loadFullSnapshot_() {
  var raw = PropertiesService.getScriptProperties()
    .getProperty('TANGTHU_DRIVE_FULL_SNAPSHOT_V3');

  if (!raw) {
    return null;
  }

  return JSON.parse(raw);
}


function saveFullSnapshot_(snapshot) {
  PropertiesService.getScriptProperties()
    .setProperty(
      'TANGTHU_DRIVE_FULL_SNAPSHOT_V3',
      JSON.stringify(snapshot)
    );
}


function loadScanState_() {
  var raw = PropertiesService.getScriptProperties()
    .getProperty(DRIVE_SCAN_STATE_KEY);

  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(
      'Drive scan state bị hỏng: ' + String(err)
    );
  }
}


function saveScanState_(state) {
  var props = PropertiesService.getScriptProperties();

  if (!state) {
    props.deleteProperty(DRIVE_SCAN_STATE_KEY);
    return;
  }

  props.setProperty(
    DRIVE_SCAN_STATE_KEY,
    JSON.stringify(state)
  );
}


function listDriveFolder_(folderId, apiKey) {
  var allFiles = [];
  var pageToken = '';

  do {
    var url =
      'https://www.googleapis.com/drive/v3/files' +
      '?q=' +
      encodeURIComponent(
        "'" + folderId + "' in parents and trashed = false"
      ) +
      '&pageSize=' + DRIVE_LIST_PAGE_SIZE +
      '&supportsAllDrives=true' +
      '&includeItemsFromAllDrives=true' +
      '&fields=' +
      encodeURIComponent(
        'nextPageToken,files(id,name,mimeType,size,createdTime,modifiedTime,md5Checksum)'
      ) +
      '&key=' + encodeURIComponent(apiKey);

    if (pageToken) {
      url += '&pageToken=' + encodeURIComponent(pageToken);
    }

    var response = UrlFetchApp.fetch(url, {
      method: 'get',
      muteHttpExceptions: true,
      headers: { Accept: 'application/json' }
    });

    var status = response.getResponseCode();
    var body = JSON.parse(
      response.getContentText() || '{}'
    );

    if (status !== 200) {
      return {
        ok: false,
        http_status: status,
        error:
          body.error && body.error.message
            ? body.error.message
            : response.getContentText()
      };
    }

    var files = body.files || [];

    for (var i = 0; i < files.length; i++) {
      allFiles.push(files[i]);
    }

    pageToken = body.nextPageToken
      ? String(body.nextPageToken)
      : '';
  } while (pageToken);

  return {
    ok: true,
    files: allFiles
  };
}


function fingerprintDriveItems_(items) {
  var rows = [];

  for (var i = 0; i < items.length; i++) {
    var f = items[i];

    rows.push([
      f.id,
      f.parent,
      f.folder ? 'D' : 'F',
      f.name,
      f.mime,
      f.size,
      f.created,
      f.modified,
      f.checksum
    ].join('\t'));
  }

  rows.sort();

  var canonical = rows.join('\n');

  var digest = Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    canonical,
    Utilities.Charset.UTF_8
  );

  var hex = '';

  for (var j = 0; j < digest.length; j++) {
    var value = digest[j];

    if (value < 0) {
      value += 256;
    }

    var h = value.toString(16);

    if (h.length < 2) {
      h = '0' + h;
    }

    hex += h;
  }

  return hex;
}


function dispatchGitHubBuild_(changedBranches) {
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
      changed_branches: changedBranches,
      dispatched_at: new Date().toISOString()
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
