/**
 * TÀNG THƯ — V4 priority scheduler
 *
 * Reuses V4 helpers already present in Code.gs:
 *   readConfig_, loadBranchState_, saveBranchState_, normalizeBranchState_,
 *   listDriveFolder_, fingerprintDriveItems_, dispatchGitHubBuild_,
 *   loadFullSnapshot_, saveFullSnapshot_, findBranchById_.
 *
 * This file owns the active driveCheck trigger after setupDrivePriorityTrigger().
 */

var PRIORITY_STATE_KEY = 'TANGTHU_DRIVE_PRIORITY_STATE_V2';
var PRIORITY_LOCK_MS = 30000;

var PRIORITY_INTERVAL_MS = {
  1: 30 * 60 * 1000,
  2: 2 * 24 * 60 * 60 * 1000,
  3: 7 * 24 * 60 * 60 * 1000
};

var PRIORITY_INITIAL_BY_BRANCH_ID = {
  // Level 1 — active / priority shelves
  'g-254dec45f9f5': 1, // Anchi
  'g-06d0e00b3242': 1, // Anki's book
  'g-c68a5b860492': 1, // BOOK
  'g-88ec7bbc132e': 1, // eNaga001
  'g-3866bf2d8817': 1, // FeliciaLee
  'g-ce119ee8fc4e': 1, // Haideng
  'g-ada02031c0e8': 1, // Harry's eBooks
  'g-9fa3e571d7a9': 1, // j test
  'g-54210b545fac': 1, // Kindle của Kai
  'g-64500837f691': 1, // Naga001
  'g-c53efe3d7bac': 1, // Ptrungtu
  'g-2d6efaf4ad21': 1, // Quin ít đọc
  'g-f1d3dceed019': 1, // Sách hay
  'g-69f1b7458b70': 1, // Tàng thư của Khang
  'g-23a8c631e3a0': 1, // Tủ sách của Ca
  'g-9effdaafa5b1': 1, // Tủ sách x3
  'g-f5a27f2a7738': 1, // Zenkjt - đang đọc

  // Level 2 — low activity
  'g-f03ca237d866': 2, // Crosspoint font
  'g-b9f7fc7f2ef5': 2, // Font ttf
  'g-25055a4c346e': 2, // My Ebook

  // Level 3 — rare / storage
  'g-d1dab15254f7': 3, // Azw3 books
  'g-b2ab7cafc708': 3, // Epub books
  'g-ca0b16750af1': 3, // Kho NCN bigg
  'g-e9c5b9a59505': 3, // Kiếm hiệp
  'g-5e02def128e3': 3, // Lịch sử
  'g-1044e1117a3b': 3, // Mobi books
  'g-299c4e2273dd': 3, // Thich Nhat Hanh
  'g-b6e2c678097a': 3  // Truyen chu
};

function priorityLog_(message) {
  Logger.log('[DrivePriority] ' + message);
}

function priorityElapsed_(startedAt) {
  return ((Date.now() - startedAt) / 1000).toFixed(1) + 's';
}

function setupDrivePriorityTrigger() {
  var lock = LockService.getScriptLock();
  lock.waitLock(PRIORITY_LOCK_MS);
  try {
    var triggers = ScriptApp.getProjectTriggers();
    var deleted = 0;

    for (var i = 0; i < triggers.length; i++) {
      if (triggers[i].getHandlerFunction() === 'driveCheck' ||
          triggers[i].getHandlerFunction() === 'driveCheckPriority') {
        ScriptApp.deleteTrigger(triggers[i]);
        deleted++;
      }
    }

    PropertiesService.getScriptProperties().deleteProperty(PRIORITY_STATE_KEY);

    ScriptApp.newTrigger('driveCheckPriority')
      .timeBased()
      .everyMinutes(30)
      .create();

    priorityLog_(
      'SETUP complete; deleted=' + deleted +
      ', trigger=driveCheckPriority, interval=30m, state=' + PRIORITY_STATE_KEY
    );

    return {ok:true, trigger:'driveCheckPriority', interval_minutes:30};
  } finally {
    lock.releaseLock();
  }
}

function driveCheckPriority() {
  var startedAt = Date.now();
  var lock = LockService.getScriptLock();

  if (!lock.tryLock(PRIORITY_LOCK_MS)) {
    priorityLog_('SKIP: another priority check is already running.');
    return {ok:false, skipped:true};
  }

  try {
    priorityLog_('START | GLOBAL_BUDGET=240000ms | CHECKPOINT=DRIVE_PAGE');

    var config = readConfig_();
    var enabled = config.branches.filter(function(b){ return b.enabled; });
    var state = loadPriorityState_(enabled);
    var force = consumeReloadQueue_();

    var counts = {1:0, 2:0, 3:0};
    enabled.forEach(function(b) {
      var e = state.branches[String(b.id)];
      counts[Number(e.priority || 1)]++;
    });

    priorityLog_(
      'SHELVES=' + enabled.length +
      ' | L1=' + counts[1] +
      ' L2=' + counts[2] +
      ' L3=' + counts[3]
    );

    var processed = 0;
    var changed = [];
    var checked = [];
    var skipped = 0;

    for (var i = 0; i < enabled.length; i++) {
      if (Date.now() - startedAt >= 4 * 60 * 1000) {
        priorityLog_('TIME BUDGET reached after ' + processed + ' shelves.');
        break;
      }

      var branch = enabled[i];
      var id = String(branch.id);
      var e = state.branches[id];
      var due = isPriorityDue_(e);
      var forced = !!force[id];

      if (!due && !forced) {
        skipped++;
        continue;
      }

      var p = Number(e.priority || 1);
      priorityLog_(
        'SCAN ' + String(branch.display_name || id) +
        ' | L' + p +
        ' | ' + (forced ? 'FORCED' : 'DUE')
      );

      var result = scanPriorityShelf_(branch, e, startedAt, false);
      if (!result.completed) {
        savePriorityState_(state);
        priorityLog_(
          'CHECKPOINT ' + String(branch.display_name || id) +
          ' | processed=' + processed +
          ' | elapsed=' + priorityElapsed_(startedAt)
        );
        return {ok:true, completed:false, processed:processed};
      }

      checked.push(id);
      processed++;

      var wasChanged = !!result.confirmed_changed;
      e.fingerprint = result.fingerprint;
      e.last_scan = new Date().toISOString();
      e.item_count = result.item_count;
      e.total_size = result.total_size;
      e.max_modified_time = result.max_modified_time;
      e.scan_queue = null;
      e.visited = {};
      e.item_count_work = 0;
      e.total_size_work = 0;
      e.max_modified_work = '';
      e.scan_folder_id = '';
      e.scan_page_token = '';
      e.full_scan_queue = null;
      e.full_visited = {};
      e.full_rows = null;
      e.full_scan_folder_id = '';
      e.full_scan_page_token = '';

      if (e.baseline_complete) {
        if (wasChanged) {
          e.change_streak = Number(e.change_streak || 0) + 1;
          e.no_change_streak = 0;

          // Finalized rule: L3 -> L2 after 2 consecutive changed scans.
          if (e.priority === 3 && e.change_streak >= 2) {
            e.priority = 2;
          }

          // L2 NEVER auto-promotes to L1.
          // L1 is manually assigned and permanently locked once assigned.

          if (e.priority === 1) e.locked = true;
          changed.push(id);

          priorityLog_(
            'RESULT ' + String(branch.display_name || id) +
            ' | CHANGED | streak=' + e.change_streak +
            ' | priority=L' + e.priority
          );
        } else {
          e.change_streak = 0;
          e.no_change_streak = Number(e.no_change_streak || 0) + 1;

          // Finalized rule: L2 -> L3 after 10 consecutive unchanged scans.
          if (e.priority === 2 && e.no_change_streak >= 10) {
            e.priority = 3;
          }

          priorityLog_(
            'RESULT ' + String(branch.display_name || id) +
            ' | UNCHANGED | no_change_streak=' + e.no_change_streak +
            ' | priority=L' + e.priority
          );
        }
      } else {
        e.baseline_complete = true;
        e.change_streak = 0;
        e.no_change_streak = 0;

        priorityLog_(
          'RESULT ' + String(branch.display_name || id) +
          ' | BASELINE | items=' + e.item_count +
          ' | size=' + e.total_size +
          ' | priority=L' + e.priority
        );
      }
    }

    savePriorityState_(state);

    if (changed.length) {
      priorityLog_(
        'DISPATCH GitHub | changed_shelves=' + changed.length +
        ' | ids=' + changed.join(',')
      );
      dispatchPriorityBuild_(changed);
    } else {
      priorityLog_('DISPATCH none');
    }

    priorityLog_(
      'END | processed=' + processed +
      ' | skipped=' + skipped +
      ' | changed=' + changed.length +
      ' | elapsed=' + priorityElapsed_(startedAt)
    );

    return {
      ok:true,
      completed:true,
      processed:processed,
      checked:checked,
      changed:changed
    };
  } finally {
    lock.releaseLock();
  }
}

function reloadShelf(e) {
  var body = e && e.action ? e : {};
  var id = String(body.branch_id || body.shelf_id || '').trim();
  if (!id) return {ok:false, error:'Thiếu branch_id.'};
  var config = readConfig_();
  var branch = findBranchById_(config, id);
  if (!branch || !branch.enabled) return {ok:false, error:'Không tìm thấy tủ sách đang hoạt động.'};

  var startedAt = Date.now();
  var state = loadPriorityState_(config.branches.filter(function(b){return b.enabled;}));
  var entry = state.branches[id];
  priorityLog_(
    'RELOAD START ' + String(branch.display_name || id) +
    ' | priority=L' + Number(entry.priority || 1)
  );

  var result = scanPriorityShelf_(branch, entry, startedAt, true);
  if (!result.completed) {
    state.branches[id] = entry;
    savePriorityState_(state);
    return {ok:true, queued:true, branch_id:id, display_name:branch.display_name, message:'Tủ quá lớn, scan đã được checkpoint; hệ thống sẽ tiếp tục tự động.'};
  }

  var oldFingerprint = entry.fingerprint || '';
  var changed = !!oldFingerprint && !!result.confirmed_changed;
  entry.fingerprint = result.fingerprint;
  entry.last_scan = new Date().toISOString();
  entry.item_count = result.item_count;
  entry.total_size = result.total_size;
  entry.max_modified_time = result.max_modified_time;
  entry.baseline_complete = true;
  entry.scan_queue = null; entry.visited = {};
  entry.item_count_work = 0; entry.total_size_work = 0; entry.max_modified_work = ''; entry.full_items_work = null;
  state.branches[id] = entry;
  savePriorityState_(state);
  if (changed) {
    priorityLog_('RELOAD DISPATCH ' + String(branch.display_name || id));
    dispatchPriorityBuild_([id]);
  } else {
    priorityLog_(
      'RELOAD END ' + String(branch.display_name || id) +
      ' | unchanged | elapsed=' + priorityElapsed_(startedAt)
    );
  }

  return {ok:true, branch_id:id, display_name:branch.display_name, changed:changed, dispatched:changed};
}

function reloadShelfById_(id) {
  return reloadShelf({branch_id:id});
}

function loadReloadQueue_() {
  var raw = PropertiesService.getScriptProperties().getProperty('TANGTHU_DRIVE_RELOAD_QUEUE_V1');
  if (!raw) return {};
  try { return JSON.parse(raw) || {}; } catch (_) { return {}; }
}
function consumeReloadQueue_() {
  var props = PropertiesService.getScriptProperties();
  var q = loadReloadQueue_();
  props.deleteProperty('TANGTHU_DRIVE_RELOAD_QUEUE_V1');
  return q;
}

function loadPriorityState_(enabled) {
  var raw = PropertiesService.getScriptProperties().getProperty(PRIORITY_STATE_KEY);
  var state = raw ? JSON.parse(raw) : {version:2, branches:{}};

  if (!state.branches) state.branches = {};

  var valid = {};
  enabled.forEach(function(b){
    var id = String(b.id);
    valid[id] = true;

    if (!state.branches[id]) {
      var priority = Number(PRIORITY_INITIAL_BY_BRANCH_ID[id] || 1);

      state.branches[id] = {
        priority: priority,
        locked: priority === 1,
        baseline_complete:false,
        fingerprint:'',
        last_scan:'',
        change_streak:0,
        no_change_streak:0,
        item_count:0,
        total_size:0,
        max_modified_time:'',
        scan_queue:null,
        visited:{},
        item_count_work:0,
        total_size_work:0,
        max_modified_work:'',
        scan_folder_id:'',
        scan_page_token:'',
        full_scan_queue:null,
        full_visited:{},
        full_digest_work:'',
        full_count_work:0,
        full_scan_folder_id:'',
        full_scan_page_token:''
      };

      priorityLog_(
        'INIT ' + String(b.display_name || id) +
        ' -> L' + priority
      );
    }
  });

  Object.keys(state.branches).forEach(function(id){
    if (!valid[id]) delete state.branches[id];
  });

  state.version = 2;
  return state;
}

function savePriorityState_(state) {
  PropertiesService.getScriptProperties().setProperty(PRIORITY_STATE_KEY, JSON.stringify(state));
}

function isPriorityDue_(e) {
  if (!e.last_scan) return true;
  var p = Number(e.priority || 1);
  return Date.now() - new Date(e.last_scan).getTime() >= PRIORITY_INTERVAL_MS[p];
}


function priorityDriveFolderPage_(folderId, pageToken, apiKey) {
  var accessToken = ScriptApp.getOAuthToken();
  var params =
    'q=' + encodeURIComponent(
      "'" + String(folderId).replace(/'/g, "\\'") + "' in parents and trashed = false"
    ) +
    '&pageSize=1000' +
    '&includeItemsFromAllDrives=true' +
    '&supportsAllDrives=true' +
    '&corpora=allDrives' +
    '&fields=' + encodeURIComponent(
      'nextPageToken,files(id,name,mimeType,size,modifiedTime,createdTime,md5Checksum)'
    );

  if (pageToken) {
    params += '&pageToken=' + encodeURIComponent(pageToken);
  }

  var response = UrlFetchApp.fetch(
    'https://www.googleapis.com/drive/v3/files?' + params,
    {
      method: 'get',
      muteHttpExceptions: true,
      headers: {
        Authorization: 'Bearer ' + accessToken,
        Accept: 'application/json'
      }
    }
  );

  var status = response.getResponseCode();
  var bodyText = response.getContentText() || '{}';
  var body;

  try {
    body = JSON.parse(bodyText);
  } catch (err) {
    body = {};
  }

  if (status !== 200) {
    return {
      ok: false,
      error: 'HTTP ' + status + ' ' + bodyText
    };
  }

  return {
    ok: true,
    files: body.files || [],
    nextPageToken: String(body.nextPageToken || '')
  };
}


function fingerprintDriveItems_(rows) {
  var normalized = (rows || []).map(function(row) {
    return [
      String(row.id || ''),
      String(row.parent || ''),
      String(row.name || ''),
      String(row.mime || ''),
      String(row.size || ''),
      String(row.modified || ''),
      String(row.created || ''),
      String(row.checksum || ''),
      row.folder ? '1' : '0'
    ].join('\u001f');
  });

  normalized.sort();

  var bytes = Utilities.newBlob(normalized.join('\n')).getBytes();
  var digest = Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    bytes
  );

  return digest.map(function(b) {
    var n = b < 0 ? b + 256 : b;
    return ('0' + n.toString(16)).slice(-2);
  }).join('');
}


function dispatchPriorityBuild_(changed) {
  var unique = {};
  (changed || []).forEach(function(id) {
    unique[String(id)] = true;
  });

  var shelves = Object.keys(unique);
  if (!shelves.length) return;

  var token = PropertiesService.getScriptProperties()
    .getProperty('TANGTHU_GITHUB_TOKEN');

  if (!token) {
    throw new Error(
      'Apps Script chưa được cấu hình TANGTHU_GITHUB_TOKEN.'
    );
  }

  var url =
    'https://api.github.com/repos/' +
    encodeURIComponent(REPO_OWNER) + '/' +
    encodeURIComponent(REPO_NAME) +
    '/dispatches';

  var payload = {
    event_type: GITHUB_DISPATCH_EVENT,
    client_payload: {
      change_count: shelves.length,
      shelves: shelves,
      detected_at: new Date().toISOString()
    }
  };

  var response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    muteHttpExceptions: true,
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    },
    payload: JSON.stringify(payload)
  });

  var status = response.getResponseCode();

  if (status < 200 || status >= 300) {
    throw new Error(
      'GitHub repository_dispatch thất bại: HTTP ' +
      status + ' ' + response.getContentText()
    );
  }

  priorityLog_(
    'GitHub repository_dispatch OK | shelves=' +
    shelves.length
  );
}


function scanPriorityShelf_(branch, entry, startedAt, forceFull) {
  var apiKey = PropertiesService.getScriptProperties().getProperty('TANGTHU_GOOGLE_API_KEY');
  if (!apiKey) throw new Error('Apps Script chưa được cấu hình TANGTHU_GOOGLE_API_KEY.');

  if (entry.full_scan_queue) {
    var resumedQuick = {
      item_count: Number(entry.item_count_work || 0),
      total_size: Number(entry.total_size_work || 0),
      max_modified_time: String(entry.max_modified_work || '')
    };
    return scanPriorityFull_(branch, entry, startedAt, apiKey, resumedQuick);
  }

  var quick = scanPriorityQuick_(branch, entry, startedAt, apiKey);
  if (!quick.completed) return quick;

  var quickChanged = !entry.baseline_complete ||
    quick.item_count !== Number(entry.item_count || 0) ||
    quick.total_size !== Number(entry.total_size || 0) ||
    quick.max_modified_time !== String(entry.max_modified_time || '');

  priorityLog_(
    'QUICK ' + String(branch.display_name || branch.id) +
    ' | items=' + quick.item_count +
    ' | size=' + quick.total_size +
    ' | max_modified=' + quick.max_modified_time +
    ' | changed=' + quickChanged
  );

  if (!forceFull && entry.baseline_complete && !quickChanged) {
    return {completed:true, confirmed_changed:false, fingerprint:entry.fingerprint || '', item_count:quick.item_count, total_size:quick.total_size, max_modified_time:quick.max_modified_time};
  }

  priorityLog_(
    'FULL ' + String(branch.display_name || branch.id) +
    ' | reason=' + (forceFull ? 'forced' : (entry.baseline_complete ? 'quick_changed' : 'baseline'))
  );

  return scanPriorityFull_(branch, entry, startedAt, apiKey, quick);
}

function scanPriorityQuick_(branch, entry, startedAt, apiKey) {
  var queue = entry.scan_queue || [String(branch.root_folder_id)];
  var visited = entry.visited || {};
  var itemCount = Number(entry.item_count_work || 0);
  var totalSize = Number(entry.total_size_work || 0);
  var maxModified = String(entry.max_modified_work || '');
  var currentFolderId = String(entry.scan_folder_id || '');
  var currentPageToken = String(entry.scan_page_token || '');

  while (true) {
    if (Date.now() - startedAt >= 4 * 60 * 1000) {
      entry.scan_queue = queue;
      entry.visited = visited;
      entry.scan_folder_id = currentFolderId;
      entry.scan_page_token = currentPageToken;
      entry.item_count_work = itemCount;
      entry.total_size_work = totalSize;
      entry.max_modified_work = maxModified;
      priorityLog_('CHECKPOINT-QUICK ' + String(branch.display_name || branch.id) +
        ' | items=' + itemCount + ' | queue=' + queue.length +
        ' | folder=' + (currentFolderId || '-') +
        ' | page_token=' + (currentPageToken ? 'yes' : 'no') +
        ' | elapsed=' + priorityElapsed_(startedAt));
      return {completed:false};
    }

    if (!currentFolderId) {
      while (queue.length && visited[String(queue[0])]) queue.shift();
      if (!queue.length) {
        return {
          completed:true,
          item_count:itemCount,
          total_size:totalSize,
          max_modified_time:maxModified
        };
      }
      currentFolderId = String(queue.shift());
      currentPageToken = '';
      if (visited[currentFolderId]) {
        currentFolderId = '';
        continue;
      }
    }

    var result = priorityDriveFolderPage_(currentFolderId, currentPageToken, apiKey);
    if (!result.ok) throw new Error('Google Drive scan thất bại: ' + result.error);

    (result.files || []).forEach(function(file) {
      itemCount++;
      if (file.size != null && file.size !== '') totalSize += Number(file.size) || 0;
      var modified = String(file.modifiedTime || '');
      if (modified > maxModified) maxModified = modified;
      if (file.mimeType === 'application/vnd.google-apps.folder') {
        queue.push(String(file.id));
      }
    });

    currentPageToken = String(result.nextPageToken || '');
    if (!currentPageToken) {
      visited[currentFolderId] = true;
      currentFolderId = '';
    }
  }
}


function digestBytesToHex_(bytes) {
  return bytes.map(function(b) {
    var n = b < 0 ? b + 256 : b;
    return ('0' + n.toString(16)).slice(-2);
  }).join('');
}

function hexToDigestBytes_(hex) {
  var bytes = [];
  hex = String(hex || '');
  for (var i = 0; i < 64; i += 2) {
    var part = hex.slice(i, i + 2);
    bytes.push(part ? parseInt(part, 16) : 0);
  }
  while (bytes.length < 32) bytes.push(0);
  return bytes.slice(0, 32);
}

function addDigestBytes_(acc, digest) {
  var out = new Array(32);
  var carry = 0;

  for (var i = 31; i >= 0; i--) {
    var sum = Number(acc[i] || 0) + Number(digest[i] || 0) + carry;
    out[i] = sum & 255;
    carry = Math.floor(sum / 256);
  }

  return out;
}

function fingerprintRow_(row) {
  var normalized = [
    String(row.id || ''),
    String(row.parent || ''),
    String(row.name || ''),
    String(row.mime || ''),
    String(row.size || ''),
    String(row.modified || ''),
    String(row.created || ''),
    String(row.checksum || ''),
    row.folder ? '1' : '0'
  ].join('\u001f');

  return Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    Utilities.newBlob(normalized).getBytes()
  ).map(function(b) {
    return b < 0 ? b + 256 : b;
  });
}

function scanPriorityFull_(branch, entry, startedAt, apiKey, quick) {
  /*
   * Full scan is resumable at Drive API page level.
   * Script Properties stores only queue/visited + current folder/page token
   * + the 32-byte digest accumulator, never the complete metadata row list.
   */
  var queue = entry.full_scan_queue || [String(branch.root_folder_id)];
  var visited = entry.full_visited || {};
  var digest = hexToDigestBytes_(entry.full_digest_work || '');
  var rowCount = Number(entry.full_count_work || 0);
  var currentFolderId = String(entry.full_scan_folder_id || '');
  var currentPageToken = String(entry.full_scan_page_token || '');

  /* Discard checkpoints from the old full_rows implementation. */
  if (entry.full_rows) {
    entry.full_rows = null;
    entry.full_scan_queue = [String(branch.root_folder_id)];
    entry.full_visited = {};
    entry.full_digest_work = '';
    entry.full_count_work = 0;
    entry.full_scan_folder_id = '';
    entry.full_scan_page_token = '';
    queue = entry.full_scan_queue;
    visited = entry.full_visited;
    digest = hexToDigestBytes_('');
    rowCount = 0;
    currentFolderId = '';
    currentPageToken = '';
  }

  while (true) {
    if (Date.now() - startedAt >= 4 * 60 * 1000) {
      entry.full_scan_queue = queue;
      entry.full_visited = visited;
      entry.full_digest_work = digestBytesToHex_(digest);
      entry.full_count_work = rowCount;
      entry.full_scan_folder_id = currentFolderId;
      entry.full_scan_page_token = currentPageToken;
      entry.full_rows = null;
      priorityLog_('CHECKPOINT-FULL ' + String(branch.display_name || branch.id) +
        ' | rows=' + rowCount + ' | queue=' + queue.length +
        ' | folder=' + (currentFolderId || '-') +
        ' | page_token=' + (currentPageToken ? 'yes' : 'no') +
        ' | elapsed=' + priorityElapsed_(startedAt));
      return {completed:false};
    }

    if (!currentFolderId) {
      while (queue.length && visited[String(queue[0])]) queue.shift();
      if (!queue.length) break;
      currentFolderId = String(queue.shift());
      currentPageToken = '';
      if (visited[currentFolderId]) {
        currentFolderId = '';
        continue;
      }
    }

    var result = priorityDriveFolderPage_(currentFolderId, currentPageToken, apiKey);
    if (!result.ok) {
      throw new Error('Google Drive full scan thất bại: ' + result.error);
    }

    (result.files || []).forEach(function(file) {
      var row = {
        id: String(file.id || ''),
        parent: currentFolderId,
        name: String(file.name || ''),
        mime: String(file.mimeType || ''),
        size: file.size == null ? '' : String(file.size),
        modified: String(file.modifiedTime || ''),
        created: String(file.createdTime || ''),
        checksum: String(file.md5Checksum || ''),
        folder: file.mimeType === 'application/vnd.google-apps.folder'
      };

      digest = addDigestBytes_(digest, fingerprintRow_(row));
      rowCount++;

      if (row.folder) queue.push(String(file.id));
    });

    currentPageToken = String(result.nextPageToken || '');
    if (!currentPageToken) {
      visited[currentFolderId] = true;
      currentFolderId = '';
    }
  }

  var fingerprint = String(rowCount) + ':' + digestBytesToHex_(digest);
  var confirmedChanged = !!entry.fingerprint && fingerprint !== entry.fingerprint;

  entry.full_scan_queue = null;
  entry.full_visited = {};
  entry.full_digest_work = '';
  entry.full_count_work = 0;
  entry.full_scan_folder_id = '';
  entry.full_scan_page_token = '';
  entry.full_rows = null;

  priorityLog_(
    'FULL DONE ' + String(branch.display_name || branch.id) +
    ' | rows=' + rowCount +
    ' | confirmed_changed=' + confirmedChanged
  );

  return {
    completed:true,
    confirmed_changed:confirmedChanged,
    fingerprint:fingerprint,
    item_count:quick.item_count,
    total_size:quick.total_size,
    max_modified_time:quick.max_modified_time
  };
}

