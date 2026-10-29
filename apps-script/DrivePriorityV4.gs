/**
 * TÀNG THƯ — V4 priority scheduler
 *
 * Levels:
 *   1 = every 30 minutes; manually controlled; never auto-demoted.
 *   2 = every 2 days; 10 unchanged scans -> Level 3.
 *   3 = every 7 days; 2 changed scans -> Level 2.
 *
 * New shelves default to Level 1.
 * Reload never changes priority.
 *
 * Depends on existing V4 helpers in Code.gs:
 *   readConfig_(), listDriveFolder_(), fingerprintDriveItems_(),
 *   dispatchGitHubBuild_(), findBranchById_()
 */

var PRIORITY_STATE_KEY = 'TANGTHU_DRIVE_PRIORITY_STATE_V2';
var PRIORITY_RELOAD_QUEUE_KEY = 'TANGTHU_DRIVE_RELOAD_QUEUE_V1';
var PRIORITY_LOCK_MS = 30000;
var PRIORITY_TIME_BUDGET_MS = 4 * 60 * 1000;
var PRIORITY_BRANCH_BUDGET_MS = 45 * 1000;

var PRIORITY_INTERVAL_MS = {
  1: 30 * 60 * 1000,
  2: 2 * 24 * 60 * 60 * 1000,
  3: 7 * 24 * 60 * 60 * 1000
};

/* Stable branch IDs for the current 28 shelves. */
var PRIORITY_INITIAL_BY_BRANCH_ID = {
  'g-f5a27f2a7738': 1,
  'g-1044e1117a3b': 3,
  'g-d1dab15254f7': 3,
  'g-e9c5b9a59505': 3,
  'g-299c4e2273dd': 3,
  'g-5e02def128e3': 3,
  'g-c68a5b860492': 1,
  'g-254dec45f9f5': 1,
  'g-b2ab7cafc708': 3,
  'g-9fa3e571d7a9': 1,
  'g-06d0e00b3242': 1,
  'g-f03ca237d866': 2,
  'g-9effdaafa5b1': 1,
  'g-3866bf2d8817': 1,
  'g-b9f7fc7f2ef5': 2,
  'g-ca0b16750af1': 3,
  'g-2d6efaf4ad21': 1,
  'g-64500837f691': 1,
  'g-69f1b7458b70': 1,
  'g-88ec7bbc132e': 1,
  'g-c53efe3d7bac': 1,
  'g-b6e2c678097a': 3,
  'g-f1d3dceed019': 1,
  'g-23a8c631e3a0': 1,
  'g-54210b545fac': 1,
  'g-25055a4c346e': 2,
  'g-ce119ee8fc4e': 1,
  'g-ada02031c0e8': 1
};

function setupDrivePriorityTrigger() {
  var lock = LockService.getScriptLock();
  lock.waitLock(PRIORITY_LOCK_MS);
  try {
    var triggers = ScriptApp.getProjectTriggers();
    for (var i = 0; i < triggers.length; i++) {
      var handler = triggers[i].getHandlerFunction();
      if (handler === 'driveCheck' || handler === 'driveCheckPriority') {
        ScriptApp.deleteTrigger(triggers[i]);
      }
    }

    var props = PropertiesService.getScriptProperties();
    props.deleteProperty('TANGTHU_DRIVE_CHANGE_STATE_V5');
    props.deleteProperty('TANGTHU_DRIVE_BRANCH_STATE_V4');
    props.deleteProperty('TANGTHU_DRIVE_SCAN_STATE_V4');
    props.deleteProperty(PRIORITY_STATE_KEY);
    props.deleteProperty(PRIORITY_RELOAD_QUEUE_KEY);

    ScriptApp.newTrigger('driveCheckPriority')
      .timeBased()
      .everyMinutes(30)
      .create();

    return {ok:true, trigger:'driveCheckPriority', interval_minutes:30};
  } finally {
    lock.releaseLock();
  }
}

function driveCheckPriority() {
  var startedAt = Date.now();
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(PRIORITY_LOCK_MS)) return {ok:true, skipped:true};

  try {
    var config = readConfig_();
    var enabled = config.branches.filter(function(b){ return b.enabled !== false; });
    var state = loadPriorityState_(enabled);
    var forced = consumeReloadQueue_();

    var processed = 0;
    var checked = [];
    var changed = [];

    var resumed = resumePendingFullScan_(config, state, startedAt);
    processed += resumed.processed;
    changed = changed.concat(resumed.changedIds);

    if (!resumed.completed) {
      savePriorityState_(state);
      dispatchChangedBranches_(changed);
      return {ok:true, completed:false, phase:'full', processed:processed, changed:changed};
    }

    for (var i = 0; i < enabled.length; i++) {
      if (Date.now() - startedAt >= PRIORITY_TIME_BUDGET_MS) break;

      var branch = enabled[i];
      var id = String(branch.id);
      var entry = state.branches[id];

      if (!isPriorityDue_(entry) && !forced[id]) continue;

      var result = scanPriorityShelf_(branch, entry, startedAt);

      if (!result.completed) {
        savePriorityState_(state);
        dispatchChangedBranches_(changed);
        return {
          ok:true, completed:false, phase:result.phase || 'quick',
          processed:processed, checked:checked, changed:changed
        };
      }

      processed++;
      checked.push(id);
      applyCompletedScan_(entry, result);
      if (result.confirmed_changed) changed.push(id);
    }

    savePriorityState_(state);
    dispatchChangedBranches_(changed);
    return {ok:true, completed:true, processed:processed, checked:checked, changed:changed};
  } finally {
    lock.releaseLock();
  }
}

function reloadShelf(body) {
  body = body || {};
  var id = String(body.branch_id || body.shelf_id || '').trim();
  if (!id) return {ok:false, error:'Thiếu branch_id.'};

  var config = readConfig_();
  var branch = findBranchById_(config, id);
  if (!branch || branch.enabled === false) {
    return {ok:false, error:'Không tìm thấy tủ sách đang hoạt động.'};
  }

  var lock = LockService.getScriptLock();
  if (!lock.tryLock(PRIORITY_LOCK_MS)) {
    enqueueReload_(id);
    return {
      ok:true, queued:true, branch_id:id, display_name:branch.display_name,
      message:'Hệ thống đang bận; tủ đã được xếp vào hàng đợi reload.'
    };
  }

  try {
    var state = loadPriorityState_(config.branches.filter(function(b){ return b.enabled !== false; }));
    var entry = state.branches[id];
    var result = scanPriorityShelf_(branch, entry, Date.now());

    if (!result.completed) {
      savePriorityState_(state);
      return {
        ok:true, queued:true, branch_id:id, display_name:branch.display_name,
        message:'Tủ lớn; scan đã checkpoint và sẽ tiếp tục tự động.'
      };
    }

    var changed = !!entry.baseline_complete && !!result.confirmed_changed;
    applyCompletedScan_(entry, result);
    savePriorityState_(state);
    if (changed) dispatchGitHubBuild_({
      change_count: 1,
      corpora: [id],
      detected_at: new Date().toISOString()
    });

    return {
      ok:true, branch_id:id, display_name:branch.display_name,
      changed:changed, dispatched:changed
    };
  } finally {
    lock.releaseLock();
  }
}

function setShelfPriority(branchId, priority) {
  var id = String(branchId || '').trim();
  var p = Number(priority);
  if (!id || (p !== 1 && p !== 2 && p !== 3)) {
    return {ok:false, error:'branch_id hoặc priority không hợp lệ.'};
  }

  var config = readConfig_();
  var branch = findBranchById_(config, id);
  if (!branch || branch.enabled === false) {
    return {ok:false, error:'Không tìm thấy tủ sách đang hoạt động.'};
  }

  var state = loadPriorityState_(config.branches.filter(function(b){ return b.enabled !== false; }));
  var entry = state.branches[id];
  entry.priority = p;
  entry.change_streak = 0;
  entry.no_change_streak = 0;
  savePriorityState_(state);

  return {ok:true, branch_id:id, display_name:branch.display_name, priority:p};
}

function enqueueReload_(id) {
  var props = PropertiesService.getScriptProperties();
  var queue = loadReloadQueue_();
  queue[id] = true;
  props.setProperty(PRIORITY_RELOAD_QUEUE_KEY, JSON.stringify(queue));
}

function loadReloadQueue_() {
  var raw = PropertiesService.getScriptProperties().getProperty(PRIORITY_RELOAD_QUEUE_KEY);
  if (!raw) return {};
  try { return JSON.parse(raw) || {}; } catch (err) { return {}; }
}

function consumeReloadQueue_() {
  var props = PropertiesService.getScriptProperties();
  var queue = loadReloadQueue_();
  props.deleteProperty(PRIORITY_RELOAD_QUEUE_KEY);
  return queue;
}

function loadPriorityState_(enabled) {
  var props = PropertiesService.getScriptProperties();
  var raw = props.getProperty(PRIORITY_STATE_KEY);
  var state = null;

  if (raw) {
    try { state = JSON.parse(raw); }
    catch (err) { throw new Error('Drive priority state bị hỏng: ' + String(err)); }
  }

  if (!state || typeof state !== 'object') state = {version:2, branches:{}};
  if (!state.branches || typeof state.branches !== 'object') state.branches = {};

  var valid = {};
  for (var i = 0; i < enabled.length; i++) {
    var branch = enabled[i];
    var id = String(branch.id);
    valid[id] = true;

    if (!state.branches[id]) {
      var configured = Number(PRIORITY_INITIAL_BY_BRANCH_ID[id]);
      var priority = (configured === 1 || configured === 2 || configured === 3) ? configured : 1;
      state.branches[id] = newPriorityEntry_(priority);
    }
  }

  Object.keys(state.branches).forEach(function(id){
    if (!valid[id]) delete state.branches[id];
  });

  state.version = 2;
  return state;
}

function newPriorityEntry_(priority) {
  return {
    priority:priority,
    baseline_complete:false,
    item_count:0,
    total_size:0,
    max_modified_time:'',
    fingerprint:'',
    last_scan:'',
    change_streak:0,
    no_change_streak:0,
    quick_queue:null,
    quick_visited:{},
    quick_item_count_work:0,
    quick_total_size_work:0,
    quick_max_modified_work:'',
    full_queue:null,
    full_visited:{},
    full_items:[],
    pending_quick_signature:null
  };
}

function isPriorityDue_(entry) {
  if (!entry.last_scan) return true;
  var p = Number(entry.priority || 1);
  if (!PRIORITY_INTERVAL_MS[p]) { p = 1; entry.priority = 1; }
  return Date.now() - new Date(entry.last_scan).getTime() >= PRIORITY_INTERVAL_MS[p];
}

function scanPriorityShelf_(branch, entry, startedAt) {
  var apiKey = PropertiesService.getScriptProperties().getProperty('TANGTHU_GOOGLE_API_KEY');
  if (!apiKey) throw new Error('Apps Script chưa được cấu hình TANGTHU_GOOGLE_API_KEY.');

  if (entry.full_queue) return continuePriorityFullScan_(branch, entry, startedAt, apiKey);

  var quick = continuePriorityQuickScan_(branch, entry, startedAt, apiKey);
  if (!quick.completed) return quick;

  var quickChanged =
    !entry.baseline_complete ||
    quick.signature.item_count !== Number(entry.item_count || 0) ||
    quick.signature.total_size !== Number(entry.total_size || 0) ||
    quick.signature.max_modified_time !== String(entry.max_modified_time || '');

  entry.pending_quick_signature = quick.signature;

  if (!entry.baseline_complete || quickChanged) {
    return startPriorityFullScan_(branch, entry, startedAt, apiKey);
  }

  entry.pending_quick_signature = null;
  return {
    completed:true,
    phase:'quick',
    confirmed_changed:false,
    signature:quick.signature,
    fingerprint:entry.fingerprint
  };
}

function continuePriorityQuickScan_(branch, entry, startedAt, apiKey) {
  var queue = entry.quick_queue;
  var visited = entry.quick_visited || {};
  var itemCount = Number(entry.quick_item_count_work || 0);
  var totalSize = Number(entry.quick_total_size_work || 0);
  var maxModified = String(entry.quick_max_modified_work || '');

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
      Date.now() - startedAt >= PRIORITY_TIME_BUDGET_MS ||
      Date.now() - branchStartedAt >= PRIORITY_BRANCH_BUDGET_MS
    ) {
      entry.quick_queue = queue;
      entry.quick_visited = visited;
      entry.quick_item_count_work = itemCount;
      entry.quick_total_size_work = totalSize;
      entry.quick_max_modified_work = maxModified;
      return {completed:false, phase:'quick'};
    }

    var folderId = queue.shift();
    if (visited[folderId]) continue;
    visited[folderId] = true;

    var result = listDriveFolder_(folderId, apiKey);
    if (!result.ok) throw new Error('Google Drive quick scan thất bại: ' + result.error);

    (result.files || []).forEach(function(file){
      itemCount++;
      if (file.size != null && file.size !== '') totalSize += Number(file.size) || 0;

      var modified = String(file.modifiedTime || '');
      if (modified > maxModified) maxModified = modified;

      if (file.mimeType === 'application/vnd.google-apps.folder') queue.push(String(file.id));
    });
  }

  entry.quick_queue = null;
  entry.quick_visited = {};
  entry.quick_item_count_work = 0;
  entry.quick_total_size_work = 0;
  entry.quick_max_modified_work = '';

  return {
    completed:true,
    phase:'quick',
    signature:{
      item_count:itemCount,
      total_size:totalSize,
      max_modified_time:maxModified
    }
  };
}

function startPriorityFullScan_(branch, entry, startedAt, apiKey) {
  entry.full_queue = [String(branch.root_folder_id)];
  entry.full_visited = {};
  entry.full_items = [];
  return continuePriorityFullScan_(branch, entry, startedAt, apiKey);
}

function continuePriorityFullScan_(branch, entry, startedAt, apiKey) {
  var queue = entry.full_queue || [];
  var visited = entry.full_visited || {};
  var items = entry.full_items || [];
  var branchStartedAt = Date.now();

  while (queue.length) {
    if (
      Date.now() - startedAt >= PRIORITY_TIME_BUDGET_MS ||
      Date.now() - branchStartedAt >= PRIORITY_BRANCH_BUDGET_MS
    ) {
      entry.full_queue = queue;
      entry.full_visited = visited;
      entry.full_items = items;
      return {completed:false, phase:'full'};
    }

    var folderId = queue.shift();
    if (visited[folderId]) continue;
    visited[folderId] = true;

    var result = listDriveFolder_(folderId, apiKey);
    if (!result.ok) throw new Error('Google Drive full scan thất bại: ' + result.error);

    (result.files || []).forEach(function(file){
      items.push({
        id:String(file.id || ''),
        parent:folderId,
        name:String(file.name || ''),
        mime:String(file.mimeType || ''),
        size:file.size == null ? '' : String(file.size),
        modified:String(file.modifiedTime || ''),
        created:String(file.createdTime || ''),
        checksum:String(file.md5Checksum || ''),
        folder:file.mimeType === 'application/vnd.google-apps.folder'
      });

      if (file.mimeType === 'application/vnd.google-apps.folder') queue.push(String(file.id));
    });
  }

  var fingerprint = fingerprintDriveItems_(items);
  var previousFingerprint = String(entry.fingerprint || '');
  var confirmedChanged =
    !!entry.baseline_complete &&
    !!previousFingerprint &&
    fingerprint !== previousFingerprint;

  entry.full_queue = null;
  entry.full_visited = {};
  entry.full_items = [];

  return {
    completed:true,
    phase:'full',
    confirmed_changed:confirmedChanged,
    signature:entry.pending_quick_signature || {
      item_count:0,
      total_size:0,
      max_modified_time:''
    },
    fingerprint:fingerprint
  };
}

function applyCompletedScan_(entry, result) {
  var previousPriority = Number(entry.priority || 1);
  var wasBaseline = !!entry.baseline_complete;
  var changed = !!result.confirmed_changed;

  entry.item_count = Number(result.signature.item_count || 0);
  entry.total_size = Number(result.signature.total_size || 0);
  entry.max_modified_time = String(result.signature.max_modified_time || '');
  entry.fingerprint = String(result.fingerprint || entry.fingerprint || '');
  entry.last_scan = new Date().toISOString();
  entry.baseline_complete = true;

  entry.quick_queue = null;
  entry.quick_visited = {};
  entry.quick_item_count_work = 0;
  entry.quick_total_size_work = 0;
  entry.quick_max_modified_work = '';
  entry.full_queue = null;
  entry.full_visited = {};
  entry.full_items = [];
  entry.pending_quick_signature = null;

  if (!wasBaseline) {
    entry.change_streak = 0;
    entry.no_change_streak = 0;
    return;
  }

  if (changed) {
    entry.change_streak = Number(entry.change_streak || 0) + 1;
    entry.no_change_streak = 0;

    if (previousPriority === 3 && entry.change_streak >= 2) {
      entry.priority = 2;
      entry.change_streak = 0;
    }
  } else {
    entry.change_streak = 0;
    entry.no_change_streak = Number(entry.no_change_streak || 0) + 1;

    if (previousPriority === 2 && entry.no_change_streak >= 10) {
      entry.priority = 3;
      entry.no_change_streak = 0;
    }
  }
}

function resumePendingFullScan_(config, state, startedAt) {
  var processed = 0;
  var changedIds = [];
  var ids = Object.keys(state.branches);

  for (var i = 0; i < ids.length; i++) {
    if (Date.now() - startedAt >= PRIORITY_TIME_BUDGET_MS) {
      return {processed:processed, changedIds:changedIds, completed:false};
    }

    var id = ids[i];
    var entry = state.branches[id];
    if (!entry.full_queue) continue;

    var branch = findBranchById_(config, id);
    if (!branch || branch.enabled === false) {
      entry.full_queue = null;
      entry.full_visited = {};
      entry.full_items = [];
      entry.pending_quick_signature = null;
      continue;
    }

    var apiKey = PropertiesService.getScriptProperties().getProperty('TANGTHU_GOOGLE_API_KEY');
    var result = continuePriorityFullScan_(branch, entry, startedAt, apiKey);

    if (!result.completed) {
      return {processed:processed, changedIds:changedIds, completed:false};
    }

    processed++;
    applyCompletedScan_(entry, result);
    if (result.confirmed_changed) changedIds.push(id);
  }

  return {processed:processed, changedIds:changedIds, completed:true};
}

function savePriorityState_(state) {
  PropertiesService.getScriptProperties()
    .setProperty(PRIORITY_STATE_KEY, JSON.stringify(state));
}

function listDriveFolder_(folderId, apiKey) {
  var allFiles = [];
  var pageToken = '';

  do {
    var url =
      'https://www.googleapis.com/drive/v3/files' +
      '?q=' +
      encodeURIComponent("'" + folderId + "' in parents and trashed = false") +
      '&pageSize=1000' +
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
      headers: {Accept: 'application/json'}
    });

    var status = response.getResponseCode();
    var body = JSON.parse(response.getContentText() || '{}');

    if (status !== 200) {
      return {
        ok: false,
        http_status: status,
        error: body.error && body.error.message
          ? body.error.message
          : response.getContentText()
      };
    }

    var files = body.files || [];
    for (var i = 0; i < files.length; i++) allFiles.push(files[i]);
    pageToken = body.nextPageToken ? String(body.nextPageToken) : '';
  } while (pageToken);

  return {ok: true, files: allFiles};
}

function fingerprintDriveItems_(items) {
  var rows = [];

  for (var i = 0; i < items.length; i++) {
    var f = items[i];
    rows.push([
      f.id, f.parent, f.folder ? 'D' : 'F', f.name, f.mime,
      f.size, f.created, f.modified, f.checksum
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
    if (value < 0) value += 256;
    var h = value.toString(16);
    if (h.length < 2) h = '0' + h;
    hex += h;
  }
  return hex;
}

function dispatchChangedBranches_(changed) {
  if (!changed || !changed.length) return;
  var unique = {};
  for (var i = 0; i < changed.length; i++) unique[String(changed[i])] = true;
  dispatchGitHubBuild_({
    change_count: Object.keys(unique).length,
    corpora: Object.keys(unique),
    detected_at: new Date().toISOString()
  });
}
