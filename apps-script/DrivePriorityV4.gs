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
  'g-69f1b7458b70': 3, // Tàng thư của Khang
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

/**
 * MANUAL PRIORITY CONTROL
 *
 * Edit only these 2 values, then Run -> setShelfPriorityManual.
 * Priority: 1 = every 30m, 2 = every 2 days, 3 = every 7 days.
 *
 * This changes the current saved priority without resetting baseline,
 * fingerprints, cursor, or any pending quick/full scan checkpoint.
 */
function setShelfPriorityManual() {
  var shelfName = 'Tàng thư của Khang';
  var newPriority = 3;

  if (![1, 2, 3].includes(Number(newPriority))) {
    throw new Error('newPriority must be 1, 2, or 3.');
  }

  var config = readConfig_();
  var branch = null;
  for (var i = 0; i < config.branches.length; i++) {
    if (String(config.branches[i].display_name || '').trim() === String(shelfName).trim()) {
      branch = config.branches[i];
      break;
    }
  }

  if (!branch) {
    throw new Error('Shelf not found: ' + shelfName);
  }

  var enabled = config.branches.filter(function(b) { return b.enabled; });
  var state = loadPriorityState_(enabled);
  var id = String(branch.id);
  var entry = state.branches[id];

  if (!entry) {
    throw new Error('Priority state not found for shelf: ' + shelfName);
  }

  var oldPriority = Number(entry.priority || 1);
  entry.priority = Number(newPriority);
  entry.locked = Number(newPriority) === 1;

  // Deliberately preserve baseline, last_scan, fingerprint and all
  // quick/full checkpoint fields. Priority is a scheduling setting only.
  savePriorityState_(state);

  priorityLog_(
    'MANUAL PRIORITY ' + shelfName +
    ' | L' + oldPriority + ' -> L' + Number(newPriority) +
    ' | baseline=' + !!entry.baseline_complete +
    ' | checkpoint=' + (hasPendingPriorityScan_(entry) ? 'PENDING' : 'NONE')
  );

  return {
    ok: true,
    shelf: shelfName,
    old_priority: oldPriority,
    new_priority: Number(newPriority),
    baseline_complete: !!entry.baseline_complete,
    checkpoint_pending: hasPendingPriorityScan_(entry)
  };
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
    var GLOBAL_BUDGET_MS = 300 * 1000;
    var SHELF_BUDGET_MS = 50 * 1000;
    priorityLog_('START | GLOBAL_BUDGET=300000ms | SHELF_BUDGET=50000ms | CHECKPOINT=DRIVE_PAGE');

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
    var skippedNames = [];
    var cursor = Number(state.cursor || 0);
    if (cursor < 0 || cursor >= enabled.length) cursor = 0;
    var roundStart = cursor;
    var visitedThisRound = 0;
    var baselineCompleteCount = enabled.filter(function(b) {
      return !!state.branches[String(b.id)].baseline_complete;
    }).length;
    priorityLog_(
      'ROUND START | cursor=' + cursor +
      ' | shelves=' + enabled.length +
      ' | baseline=' + baselineCompleteCount + '/' + enabled.length
    );

    while (visitedThisRound < enabled.length) {
      if (Date.now() - startedAt >= GLOBAL_BUDGET_MS) {
        priorityLog_('TIME BUDGET reached after ' + processed + ' shelves | cursor=' + cursor);
        break;
      }

      var branch = enabled[cursor];
      var id = String(branch.id);
      var e = state.branches[id];
      var p = Number(e.priority || 1);
      // Existing shelves without a page snapshot must be migrated once,
      // regardless of their normal L1/L2/L3 interval.
      var due = isPriorityDue_(e) || !e.snapshot_available;
      var forced = !!force[id];
      var pending = hasPendingPriorityScan_(e);

      // A pending scan always resumes first, regardless of priority or due time.
      if (!pending && !due && !forced) {
        skipped++;
        skippedNames.push(String(branch.display_name || id) + ' L' + p);
        priorityLog_(
          'SKIP ' + String(branch.display_name || id) +
          ' | L' + p +
          ' | ' + (e.baseline_complete ? 'BASELINE_DONE' : 'NOT_DUE')
        );
        cursor = (cursor + 1) % enabled.length;
        visitedThisRound++;
        continue;
      }

      priorityLog_(
        'SCAN ' + String(branch.display_name || id) +
        ' | L' + p +
        ' | ' + (pending ? 'RESUME' : (forced ? 'FORCED' : (!e.snapshot_available ? 'SNAPSHOT_BOOTSTRAP' : 'DUE')))
      );

      var shelfStartedAt = Date.now();
      var hadSnapshotBeforeScan = !!e.snapshot_available;
      var result;
      try {
        result = scanPriorityShelf_(branch, e, shelfStartedAt, false, SHELF_BUDGET_MS, GLOBAL_BUDGET_MS, startedAt);
      } catch (scanError) {
        // Preserve the active generation and exact Drive page cursor on failure.
        // A failed/ambiguous PUT is retried on the next run using the same R2 key.
        state.cursor = cursor;
        try {
          savePriorityState_(state);
          priorityLog_('ERROR CHECKPOINT SAVED | branch=' + id +
            ' | generation=' + String(e.r2_snapshot_generation_id || '-') +
            ' | pages=' + ((e.r2_snapshot_page_keys || []).length) +
            ' | folder=' + String(e.full_scan_folder_id || '-') +
            ' | page_token=' + (e.full_scan_page_token ? 'yes' : 'no'));
        } catch (checkpointError) {
          priorityLog_('ERROR CHECKPOINT SAVE FAILED | branch=' + id +
            ' | ' + String(checkpointError));
        }
        throw scanError;
      }

      // The shelf budget is local to this shelf. Checkpoint and move the cursor;
      // do NOT return from the execution. This is the key V4 behavior.
      if (!result.completed) {
        // The active R2 manifest still points to the last complete generation.
        // A partial generation is private staging data and must not trigger a build.
        priorityLog_('PARTIAL SNAPSHOT STAGED ' + String(branch.display_name || id) +
          ' | active_snapshot_preserved=' + !!e.snapshot_available +
          ' | staged_items=' + Number(e.snapshot_item_count || 0) +
          ' | staged_pages=' + (e.r2_snapshot_page_keys || []).length);
        state.cursor = (cursor + 1) % enabled.length;
        savePriorityState_(state);
        priorityLog_(
          'CHECKPOINT ' + String(branch.display_name || id) +
          ' | processed=' + processed +
          ' | next_cursor=' + state.cursor +
          ' | elapsed=' + priorityElapsed_(startedAt)
        );
        cursor = state.cursor;
        visitedThisRound++;
        continue;
      }

      checked.push(id);
      processed++;

      var wasChanged = !!result.confirmed_changed;
      var snapshotBootstrapped = !hadSnapshotBeforeScan && !!e.snapshot_available;
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

      if (snapshotBootstrapped && changed.indexOf(id) < 0) {
        changed.push(id);
        priorityLog_('SNAPSHOT BOOTSTRAPPED ' + String(branch.display_name || id));
      }

      if (e.baseline_complete) {
        if (wasChanged) {
          e.change_streak = Number(e.change_streak || 0) + 1;
          e.no_change_streak = 0;

          if (e.priority === 3 && e.change_streak >= 2) {
            e.priority = 2;
          }

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
        e.snapshot_complete = true;
        e.change_streak = 0;
        e.no_change_streak = 0;
        if (changed.indexOf(id) < 0) changed.push(id);

        priorityLog_(
          'RESULT ' + String(branch.display_name || id) +
          ' | BASELINE | items=' + e.item_count +
          ' | size=' + e.total_size +
          ' | priority=L' + e.priority
        );
      }

      state.cursor = (cursor + 1) % enabled.length;
      savePriorityState_(state);
      cursor = state.cursor;
      visitedThisRound++;

      // If the global budget was crossed during the completed shelf, stop here.
      if (Date.now() - startedAt >= GLOBAL_BUDGET_MS) {
        priorityLog_('TIME BUDGET reached after ' + processed + ' shelves | cursor=' + cursor);
        break;
      }
    }

    state.cursor = cursor;
    savePriorityState_(state);

    priorityLog_(
      'ROUND END | processed=' + processed +
      ' | skipped=' + skipped +
      ' | changed=' + changed.length +
      ' | next_cursor=' + cursor +
      ' | elapsed=' + priorityElapsed_(startedAt)
    );
    if (skippedNames.length) {
      priorityLog_('SKIP LIST | ' + skippedNames.join(' | '));
    }

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
      ' | next_cursor=' + cursor +
      ' | elapsed=' + priorityElapsed_(startedAt)
    );

    return {
      ok:true,
      completed:true,
      processed:processed,
      checked:checked,
      changed:changed,
      skipped:skipped,
      cursor:cursor
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

  var hadSnapshotBeforeReload = !!entry.snapshot_available;
  var result = scanPriorityShelf_(branch, entry, startedAt, true, 50 * 1000, 300 * 1000, startedAt);
  if (!result.completed) {
    state.branches[id] = entry;
    savePriorityState_(state);
    return {ok:true, queued:true, branch_id:id, display_name:branch.display_name, message:'Tủ lớn; generation mới đang được dựng ở chế độ staging. Bản snapshot đang hoạt động vẫn được giữ nguyên cho đến khi quét hoàn tất.'};
  }

  var oldFingerprint = entry.fingerprint || '';
  var changed = !!oldFingerprint && !!result.confirmed_changed;
  entry.fingerprint = result.fingerprint;
  entry.last_scan = new Date().toISOString();
  entry.item_count = result.item_count;
  entry.total_size = result.total_size;
  entry.max_modified_time = result.max_modified_time;
  entry.baseline_complete = true;
  entry.snapshot_complete = true;
  entry.scan_queue = null; entry.visited = {};
  entry.item_count_work = 0; entry.total_size_work = 0; entry.max_modified_work = ''; entry.full_items_work = null;
  state.branches[id] = entry;
  savePriorityState_(state);
  if (changed || !hadSnapshotBeforeReload) {
    priorityLog_('RELOAD DISPATCH ' + String(branch.display_name || id) +
      ' | changed=' + changed + ' | snapshot_bootstrapped=' + !hadSnapshotBeforeReload);
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

var PRIORITY_STATE_FILE_KEY = 'TANGTHU_DRIVE_PRIORITY_STATE_FILE_ID';
var PRIORITY_STATE_FILE_NAME = 'TANGTHU_DRIVE_PRIORITY_STATE_V2.json';

/**
 * Large scan checkpoints belong in a Drive file, not Script Properties.
 * Script Properties has a small per-value and total storage quota.
 */
function loadPriorityStateRaw_() {
  var props = PropertiesService.getScriptProperties();
  var fileId = props.getProperty(PRIORITY_STATE_FILE_KEY);
  var file = null;
  var folder = tangThuSystemFolder_();

  if (fileId) {
    try {
      file = DriveApp.getFileById(fileId);
      file.moveTo(folder);
      return file.getBlob().getDataAsString('UTF-8');
    } catch (err) {
      priorityLog_('STATE FILE pointer unavailable; searching TangThu_System and legacy root.');
    }
  }

  var files = folder.getFilesByName(PRIORITY_STATE_FILE_NAME);
  if (files.hasNext()) {
    file = files.next();
    props.setProperty(PRIORITY_STATE_FILE_KEY, file.getId());
    return file.getBlob().getDataAsString('UTF-8');
  }

  files = DriveApp.getRootFolder().getFilesByName(PRIORITY_STATE_FILE_NAME);
  if (files.hasNext()) {
    file = files.next();
    file.moveTo(folder);
    props.setProperty(PRIORITY_STATE_FILE_KEY, file.getId());
    return file.getBlob().getDataAsString('UTF-8');
  }

  return props.getProperty(PRIORITY_STATE_KEY);
}

function savePriorityStateRaw_(raw) {
  var props = PropertiesService.getScriptProperties();
  var fileId = props.getProperty(PRIORITY_STATE_FILE_KEY);
  var file = null;
  var folder = tangThuSystemFolder_();

  if (fileId) {
    try {
      file = DriveApp.getFileById(fileId);
      file.moveTo(folder);
      file.setContent(raw);
      return;
    } catch (err) {
      priorityLog_('STATE FILE unavailable; searching TangThu_System.');
    }
  }

  var files = folder.getFilesByName(PRIORITY_STATE_FILE_NAME);
  if (files.hasNext()) {
    file = files.next();
    file.setContent(raw);
  } else {
    files = DriveApp.getRootFolder().getFilesByName(PRIORITY_STATE_FILE_NAME);
    if (files.hasNext()) {
      file = files.next();
      file.moveTo(folder);
      file.setContent(raw);
    } else {
      file = folder.createFile(PRIORITY_STATE_FILE_NAME, raw, MimeType.PLAIN_TEXT);
    }
  }

  props.deleteProperty(PRIORITY_STATE_KEY);
  props.setProperty(PRIORITY_STATE_FILE_KEY, file.getId());
}

function loadPriorityState_(enabled) {
  var raw = loadPriorityStateRaw_();
  var state = raw ? JSON.parse(raw) : {version:2, cursor:0, branches:{}};

  if (!state.branches) state.branches = {};
  if (state.cursor == null) state.cursor = 0;

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

  state.version = 3;
  return state;
}

function savePriorityState_(state) {
  savePriorityStateRaw_(JSON.stringify(state));
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
      'nextPageToken,files(id,name,mimeType,size,modifiedTime,createdTime,md5Checksum,webContentLink)'
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


function hasPendingPriorityScan_(entry) {
  return !!(entry.scan_queue || entry.full_scan_queue || entry.scan_folder_id || entry.full_scan_folder_id || entry.scan_page_token || entry.full_scan_page_token);
}

function scanPriorityShelf_(branch, entry, shelfStartedAt, forceFull, shelfBudgetMs, globalBudgetMs, globalStartedAt) {
  var apiKey = PropertiesService.getScriptProperties().getProperty('TANGTHU_GOOGLE_API_KEY');
  if (!apiKey) throw new Error('Apps Script chưa được cấu hình TANGTHU_GOOGLE_API_KEY.');

  if (entry.full_scan_queue) {
    var resumedQuick = {
      item_count: Number(entry.item_count_work || 0),
      total_size: Number(entry.total_size_work || 0),
      max_modified_time: String(entry.max_modified_work || '')
    };
    return scanPriorityFull_(branch, entry, shelfStartedAt, apiKey, resumedQuick, shelfBudgetMs, globalBudgetMs, globalStartedAt);
  }

  // Initial baseline is a single resumable FULL scan. Do not spend a second
  // complete traversal on QUICK before any complete fingerprint exists.
  if (!entry.baseline_complete || !entry.snapshot_available) {
    priorityLog_('BASELINE/SNAPSHOT START ' + String(branch.display_name || branch.id) +
      ' | baseline=' + (entry.baseline_complete ? 'DONE' : 'PENDING') +
      ' | snapshot=' + (entry.snapshot_available ? 'RESUME' : 'NEW'));
    return scanPriorityFull_(branch, entry, shelfStartedAt, apiKey,
      {item_count:0,total_size:0,max_modified_time:''},
      shelfBudgetMs, globalBudgetMs, globalStartedAt);
  }

  var quick = scanPriorityQuick_(branch, entry, shelfStartedAt, apiKey, shelfBudgetMs, globalBudgetMs, globalStartedAt);
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

  return scanPriorityFull_(branch, entry, shelfStartedAt, apiKey, quick, shelfBudgetMs, globalBudgetMs, globalStartedAt);
}

function scanPriorityQuick_(branch, entry, shelfStartedAt, apiKey, shelfBudgetMs, globalBudgetMs, globalStartedAt) {
  var queue = entry.scan_queue || [String(branch.root_folder_id)];
  var visited = entry.visited || {};
  var itemCount = Number(entry.item_count_work || 0);
  var totalSize = Number(entry.total_size_work || 0);
  var maxModified = String(entry.max_modified_work || '');
  var currentFolderId = String(entry.scan_folder_id || '');
  var currentPageToken = String(entry.scan_page_token || '');

  while (true) {
    // Finish a drained queue before checking the time budget.
    // This prevents a completed scan from being checkpointed as pending.
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
    }

    if ((Date.now() - globalStartedAt) >= globalBudgetMs || (Date.now() - shelfStartedAt) >= shelfBudgetMs) {
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
        ' | shelf_elapsed=' + priorityElapsed_(shelfStartedAt) +
        ' | global_elapsed=' + priorityElapsed_(globalStartedAt));
      return {completed:false};
    }

    if (!currentFolderId) {
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

var SNAPSHOT_MIME = MimeType.PLAIN_TEXT;

// All V4 operational files live in this existing Drive folder.
var TANGTHU_SYSTEM_FOLDER_ID = '1Sjwq0ciRZXmEuIA4JGc_0aE3i2HWkioo';

function tangThuSystemFolder_() {
  return DriveApp.getFolderById(TANGTHU_SYSTEM_FOLDER_ID);
}

/**
 * One-time, non-destructive migration.
 * Moves only V4 state/snapshot files from My Drive root into TangThu_System.
 * Existing Drive file IDs and sharing permissions are preserved.
 * Does not alter triggers, Script Properties, scan checkpoints or fingerprints.
 */
function migratePriorityFilesToSystemFolder() {
  var folder = tangThuSystemFolder_();
  var root = DriveApp.getRootFolder();
  var moved = 0;
  var failed = [];
  var files = root.getFiles();

  while (files.hasNext()) {
    var file = files.next();
    var name = String(file.getName() || '');
    if (name !== PRIORITY_STATE_FILE_NAME && name.indexOf('TANGTHU_SNAPSHOT_') !== 0) continue;

    try {
      file.moveTo(folder);
      moved++;
      priorityLog_('MIGRATE TO TangThu_System | ' + name + ' | id=' + file.getId());
    } catch (err) {
      failed.push(name + ' [' + file.getId() + ']: ' + String(err));
      priorityLog_('MIGRATE FAILED | ' + name + ' | id=' + file.getId() + ' | ' + String(err));
    }
  }

  var stateFiles = folder.getFilesByName(PRIORITY_STATE_FILE_NAME);
  return {
    ok: failed.length === 0,
    folder_id: TANGTHU_SYSTEM_FOLDER_ID,
    moved: moved,
    state_file_in_destination: stateFiles.hasNext(),
    failed: failed
  };
}

/**
 * Cloudflare R2 snapshot V2 adapter.
 *
 * Safe rollout gate:
 *   TANGTHU_R2_SNAPSHOT_ENABLED = "true"
 *
 * Required Script Properties when enabled:
 *   TANGTHU_R2_API_URL   = https://tangthu-storage-api.mienluonngon.workers.dev
 *   TANGTHU_R2_API_TOKEN = the Worker bearer token
 *
 * Every full scan starts a fresh R2 generation. Legacy scan cursors are
 * discarded; snapshot pages and the final manifest are written only to R2.
 * Google Drive is not used as a snapshot destination.
 */
function r2SnapshotEnabled_() {
  return String(PropertiesService.getScriptProperties()
    .getProperty('TANGTHU_R2_SNAPSHOT_ENABLED') || '').toLowerCase() === 'true';
}

function r2SnapshotPut_(key, content) {
  var props = PropertiesService.getScriptProperties();
  var baseUrl = String(props.getProperty('TANGTHU_R2_API_URL') || '').replace(/\/+$/, '');
  var token = String(props.getProperty('TANGTHU_R2_API_TOKEN') || '');
  if (!baseUrl || !token) {
    throw new Error('Thiếu Script Properties TANGTHU_R2_API_URL hoặc TANGTHU_R2_API_TOKEN');
  }

  var encodedKey = String(key).split('/').map(encodeURIComponent).join('/');
  var url = baseUrl + '/v1/objects/' + encodedKey;
  var maxAttempts = 4;
  var delays = [1000, 2000, 4000];
  var lastError = null;

  for (var attempt = 1; attempt <= maxAttempts; attempt++) {
    var started = Date.now();
    try {
      var response = UrlFetchApp.fetch(url, {
        method: 'put',
        contentType: 'application/json',
        payload: content,
        headers: {Authorization: 'Bearer ' + token},
        muteHttpExceptions: true
      });
      var status = response.getResponseCode();
      var elapsed = Date.now() - started;

      if (status >= 200 && status < 300) {
        priorityLog_('R2 PUT OK | attempt=' + attempt + '/' + maxAttempts +
          ' | HTTP=' + status + ' | ms=' + elapsed + ' | key=' + key);
        return key;
      }

      var body = response.getContentText().slice(0, 500);
      var retryable = status === 408 || status === 429 || status >= 500;
      lastError = new Error('R2 PUT HTTP ' + status + ': ' + body);
      priorityLog_('R2 PUT HTTP ERROR | attempt=' + attempt + '/' + maxAttempts +
        ' | HTTP=' + status + ' | ms=' + elapsed + ' | retry=' + retryable + ' | key=' + key);
      if (!retryable || attempt === maxAttempts) throw lastError;
    } catch (err) {
      // Transport exceptions (e.g. Address unavailable) have no HTTP response.
      // HTTP errors created above are retried only for 408/429/5xx.
      if (lastError && err === lastError) throw err;
      lastError = err;
      priorityLog_('R2 PUT TRANSPORT ERROR | attempt=' + attempt + '/' + maxAttempts +
        ' | ms=' + (Date.now() - started) + ' | error=' + String(err).slice(0, 300) +
        ' | key=' + key);
      if (attempt === maxAttempts) {
        throw new Error('R2 PUT không kết nối được sau ' + maxAttempts +
          ' lần thử | key=' + key + ' | lỗi cuối: ' + String(lastError));
      }
    }

    Utilities.sleep(delays[attempt - 1]);
  }
  throw lastError || new Error('R2 PUT thất bại không rõ nguyên nhân: ' + key);
}

function r2SnapshotWritePage_(branch, entry, items) {
  var generation = String(entry.r2_snapshot_generation_id || '');
  if (!generation) return null; // Legacy in-flight scan: do not publish a partial R2 generation.

  var pageIndex = Number(entry.r2_snapshot_page_keys.length || 0) + 1;
  var key = 'snapshots/' + String(branch.id) + '/generations/' + generation +
    '/pages/page-' + ('000000' + pageIndex).slice(-6) + '.json';
  r2SnapshotPut_(key, JSON.stringify({items: items}));
  entry.r2_snapshot_page_keys.push(key);
  return key;
}

function r2SnapshotPublishManifest_(branch, entry, complete) {
  var generation = String(entry.r2_snapshot_generation_id || '');
  if (!generation) return false;
  var pages = (entry.r2_snapshot_page_keys || []).slice();
  var manifest = {
    version: 2,
    storage: 'r2',
    branch_id: String(branch.id),
    folder_name: String(branch.display_name || ''),
    generation_id: generation,
    complete: complete === true,
    page_count: pages.length,
    pages: pages,
    item_count: Number(entry.snapshot_item_count || 0),
    updated_at: new Date().toISOString()
  };

  if (manifest.page_count === 0 && manifest.item_count !== 0) {
    throw new Error('R2 manifest không hợp lệ: có item nhưng không có page');
  }
  r2SnapshotPut_('snapshots/' + String(branch.id) + '/manifest.json', JSON.stringify(manifest));
  priorityLog_('R2 SNAPSHOT PUBLISHED | branch=' + branch.id +
    ' | generation=' + generation + ' | pages=' + manifest.page_count +
    ' | items=' + manifest.item_count);
  return true;
}

function snapshotPersistPage_(branch, entry, folderId, files) {
  var generation = String(entry.r2_snapshot_generation_id || '');
  if (!generation) {
    throw new Error('R2 snapshot chưa được khởi tạo; từ chối ghi snapshot lên Google Drive.');
  }
  if (!Array.isArray(entry.r2_snapshot_page_keys)) entry.r2_snapshot_page_keys = [];

  var items = (files || []).map(function(file) {
    return {
      id: String(file.id || ''),
      parent_id: String(folderId || ''),
      name: String(file.name || ''),
      mime: String(file.mimeType || ''),
      size: file.size == null ? 0 : Number(file.size),
      modified: String(file.modifiedTime || ''),
      checksum: String(file.md5Checksum || ''),
      folder: file.mimeType === 'application/vnd.google-apps.folder',
      web_content_link: String(file.webContentLink || '')
    };
  });
  if (!items.length) return;

  r2SnapshotWritePage_(branch, entry, items);
  entry.snapshot_page_index = Number(entry.snapshot_page_index || 0) + 1;
  entry.snapshot_item_count = Number(entry.snapshot_item_count || 0) + items.length;
}

function scanPriorityFull_(branch, entry, shelfStartedAt, apiKey, quick, shelfBudgetMs, globalBudgetMs, globalStartedAt) {
  /*
   * Full scan is resumable at Drive API page level.
   * Script Properties stores only queue/visited + current folder/page token
   * + the 32-byte digest accumulator, never the complete metadata row list.
   */
  // Start a completely new scan whenever there is no active R2 generation.
  // This intentionally discards every legacy/in-flight scan cursor and starts
  // again at the branch root. The checkpoint remains resumable after this
  // fresh generation has been saved by the caller.
  if (!r2SnapshotEnabled_()) {
    throw new Error('R2 snapshot đang tắt. Không cho phép fallback ghi snapshot lên Google Drive.');
  }
  if (!entry.r2_snapshot_generation_id) {
    entry.snapshot_scan_id = Utilities.getUuid().replace(/-/g, '');
    entry.r2_snapshot_generation_id = entry.snapshot_scan_id;
    entry.r2_snapshot_page_keys = [];
    entry.snapshot_page_index = 0;
    entry.snapshot_item_count = 0;
    entry.item_count_work = 0;
    entry.total_size_work = 0;
    entry.max_modified_work = '';
    entry.scan_queue = null;
    entry.visited = {};
    entry.scan_folder_id = '';
    entry.scan_page_token = '';

    // Discard old full-scan checkpoints; preserve configuration, fingerprint
    // baseline and scheduler metadata. No old Drive snapshot is read or deleted.
    entry.full_scan_queue = [String(branch.root_folder_id)];
    entry.full_visited = {};
    entry.full_digest_work = '';
    entry.full_count_work = 0;
    entry.full_scan_folder_id = '';
    entry.full_scan_page_token = '';
    entry.full_rows = null;

    // Do not retain legacy Drive snapshot pointers in the active snapshot state.
    entry.snapshot_page_file_ids = [];
    entry.snapshot_previous_page_file_ids = [];
    // Keep the active-snapshot flags unchanged. The new generation is only
    // staging data until its final manifest is published.

    priorityLog_('R2 FRESH SCAN START | branch=' + branch.id +
      ' | generation=' + entry.r2_snapshot_generation_id + ' | old scan checkpoint discarded');
  }
  if (!Array.isArray(entry.r2_snapshot_page_keys)) entry.r2_snapshot_page_keys = [];
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
    // Finish a drained queue before checking the time budget.
    // This prevents a completed scan from being checkpointed as pending.
    if (!currentFolderId) {
      while (queue.length && visited[String(queue[0])]) queue.shift();
      if (!queue.length) break;
    }

    if ((Date.now() - globalStartedAt) >= globalBudgetMs || (Date.now() - shelfStartedAt) >= shelfBudgetMs) {
      entry.full_scan_queue = queue;
      entry.full_visited = visited;
      entry.full_digest_work = digestBytesToHex_(digest);
      entry.full_count_work = rowCount;
      entry.full_scan_folder_id = currentFolderId;
      entry.full_scan_page_token = currentPageToken;
      entry.full_rows = null;
      // Keep the current manifest and active-snapshot flags untouched while
      // the new generation is staged. Only a completed scan may replace them.
      priorityLog_('CHECKPOINT-FULL ' + String(branch.display_name || branch.id) +
        ' | rows=' + rowCount + ' | queue=' + queue.length +
        ' | folder=' + (currentFolderId || '-') +
        ' | page_token=' + (currentPageToken ? 'yes' : 'no') +
        ' | shelf_elapsed=' + priorityElapsed_(shelfStartedAt) +
        ' | global_elapsed=' + priorityElapsed_(globalStartedAt));
      return {completed:false};
    }

    if (!currentFolderId) {
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

    // Persist the cursor BEFORE the R2 PUT. If the request fails or the
    // response is lost, the next execution re-fetches this exact Drive page.
    // r2SnapshotWritePage_ uses the next uncommitted page key, so the PUT is
    // safely repeatable for the same page/generation.
    entry.full_scan_queue = queue;
    entry.full_visited = visited;
    entry.full_digest_work = digestBytesToHex_(digest);
    entry.full_count_work = rowCount;
    entry.full_scan_folder_id = currentFolderId;
    entry.full_scan_page_token = currentPageToken;
    entry.full_rows = null;

    snapshotPersistPage_(branch, entry, currentFolderId, result.files || []);

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

  // R2 is the only snapshot destination. Publish only after the full scan ends.
  r2SnapshotPublishManifest_(branch, entry, true);
  entry.snapshot_available = true;
  entry.snapshot_complete = true;
  entry.r2_snapshot_generation_id = '';
  entry.r2_snapshot_page_keys = [];
  entry.snapshot_previous_page_file_ids = [];
  priorityLog_('R2 SNAPSHOT ACTIVE | branch=' + branch.id + ' | snapshot stored only in R2');

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

