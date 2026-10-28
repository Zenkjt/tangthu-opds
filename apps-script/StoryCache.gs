/**
 * TÀNG THƯ — Story shelf-local cache API
 *
 * This file is an addition to the Apps Script project.
 * It does NOT replace Code.gs and deliberately contains no doPost().
 * Code.gs must route action === 'story_cache' to storyCache_(body).
 *
 * Drive layout:
 *   <shelf root>/StoryState
 *   <shelf root>/ZtangthuCache/<story_id>/entry_NNN.json
 *
 * No list/scan/TTL/LRU/GC operation is exposed.
 */

var STORY_CACHE_FOLDER_NAME = 'ZtangthuCache';
var STORY_STATE_FILENAME = 'StoryState';
var STORY_CACHE_MAX_BASE64 = 45 * 1024 * 1024;
var STORY_CACHE_MIME = 'application/json';

function storyCache_(body) {
  var props = PropertiesService.getScriptProperties();
  var expectedToken = String(props.getProperty('TANGTHU_UPLOAD_TOKEN') || '');
  var suppliedToken = String(body.token || '');

  if (!expectedToken || suppliedToken !== expectedToken) {
    return { ok: false, error: 'Unauthorized story cache request.' };
  }

  var folderId = String(body.folder_id || '').trim();
  if (!folderId) {
    return { ok: false, error: 'Missing shelf folder.' };
  }

  var shelf = storyCacheShelf_(folderId);
  if (!shelf.ok) return shelf;

  var operation = String(body.operation || '').trim().toLowerCase();

  if (operation === 'ensure') {
    var storyId = storyCacheComponent_(body.story_id);
    if (!storyId) {
      return { ok: false, error: 'Missing story_id.' };
    }

    var cacheFolder = storyCacheFindOrCreateFolder_(
      shelf.folder,
      STORY_CACHE_FOLDER_NAME
    );
    var storyFolder = storyCacheFindOrCreateFolder_(cacheFolder, storyId);

    return {
      ok: true,
      cache_folder_id: cacheFolder.getId(),
      story_folder_id: storyFolder.getId()
    };
  }

  if (operation === 'read') {
    var readPath = storyCacheValidatePath_(body.relative_path);
    if (!readPath.ok) return readPath;

    var readFile = storyCacheResolveFile_(shelf.folder, readPath.parts);
    if (!readFile) {
      return { ok: true, exists: false };
    }

    var blob = readFile.getBlob();
    var bytes = blob.getBytes();

    return {
      ok: true,
      exists: true,
      filename: readFile.getName(),
      mime_type: blob.getContentType() || STORY_CACHE_MIME,
      content_base64: Utilities.base64Encode(bytes)
    };
  }

  if (operation === 'write') {
    var writePath = storyCacheValidatePath_(body.relative_path);
    if (!writePath.ok) return writePath;

    var encoded = String(body.content_base64 || '');
    if (!encoded) {
      return { ok: false, error: 'Missing content_base64.' };
    }
    if (encoded.length > STORY_CACHE_MAX_BASE64) {
      return { ok: false, error: 'Story cache payload is too large.' };
    }

    var bytes;
    try {
      bytes = Utilities.base64Decode(encoded);
    } catch (err) {
      return { ok: false, error: 'Invalid base64 payload.' };
    }
    if (!bytes.length) {
      return { ok: false, error: 'Empty story cache payload.' };
    }

    var parent = storyCacheEnsureParent_(shelf.folder, writePath.parts);
    var filename = writePath.parts[writePath.parts.length - 1];
    var mimeType = String(body.mime_type || 'application/octet-stream');
    var blob = Utilities.newBlob(bytes, mimeType, filename);
    var existing = storyCacheFindFile_(parent, filename);

    if (existing) {
      // DriveApp has no binary setBlob() update method. Replace the cache
      // artifact; cache file IDs are intentionally not part of the API.
      existing.setTrashed(true);
      var replacement = parent.createFile(blob);
      return {
        ok: true,
        file_id: replacement.getId(),
        path: writePath.path
      };
    }

    var created = parent.createFile(blob);
    return {
      ok: true,
      file_id: created.getId(),
      path: writePath.path
    };
  }

  return { ok: false, error: 'Unsupported story_cache operation.' };
}

function storyCacheShelf_(folderId) {
  var config = readConfig_();
  var branch = null;

  for (var i = 0; i < config.branches.length; i++) {
    var item = config.branches[i];
    if (
      String(item.root_folder_id) === folderId &&
      item.enabled !== false
    ) {
      branch = item;
      break;
    }
  }

  if (!branch) {
    return {
      ok: false,
      error: 'Target folder is not an active registered Tàng Thư shelf.'
    };
  }

  try {
    return { ok: true, folder: DriveApp.getFolderById(folderId), branch: branch };
  } catch (err) {
    return {
      ok: false,
      error: 'Apps Script cannot access this shelf: ' + String(err)
    };
  }
}

function storyCacheComponent_(value) {
  var valueText = String(value || '').trim();
  if (!valueText || valueText === '.' || valueText === '..') return '';
  if (!/^[A-Za-z0-9._-]+$/.test(valueText)) return '';
  return valueText;
}

function storyCacheValidatePath_(value) {
  var path = String(value || '').trim();
  if (!path || path.indexOf('\\') >= 0) {
    return { ok: false, error: 'Invalid story cache path.' };
  }

  var rawParts = path.split('/');
  if (!rawParts.length) {
    return { ok: false, error: 'Invalid story cache path.' };
  }

  if (rawParts[0] === STORY_STATE_FILENAME) {
    if (rawParts.length !== 1) {
      return { ok: false, error: 'Invalid StoryState path.' };
    }
    return { ok: true, parts: rawParts, path: path };
  }

  if (rawParts[0] !== STORY_CACHE_FOLDER_NAME || rawParts.length !== 3) {
    return { ok: false, error: 'Path must target StoryState or ZtangthuCache/<story_id>/<file>.' };
  }

  for (var i = 1; i < rawParts.length; i++) {
    if (!storyCacheComponent_(rawParts[i])) {
      return { ok: false, error: 'Invalid story cache path component.' };
    }
  }

  return { ok: true, parts: rawParts, path: path };
}

function storyCacheFindOrCreateFolder_(parent, name) {
  var folders = parent.getFoldersByName(name);
  if (folders.hasNext()) return folders.next();
  return parent.createFolder(name);
}

function storyCacheFindFile_(parent, filename) {
  var files = parent.getFilesByName(filename);
  return files.hasNext() ? files.next() : null;
}

function storyCacheEnsureParent_(root, parts) {
  if (parts.length === 1) return root;

  var cache = storyCacheFindOrCreateFolder_(root, parts[0]);
  return storyCacheFindOrCreateFolder_(cache, parts[1]);
}

function storyCacheResolveFile_(root, parts) {
  if (parts.length === 1) {
    return storyCacheFindFile_(root, parts[0]);
  }

  var cacheFolders = root.getFoldersByName(parts[0]);
  if (!cacheFolders.hasNext()) return null;
  var cache = cacheFolders.next();

  var storyFolders = cache.getFoldersByName(parts[1]);
  if (!storyFolders.hasNext()) return null;
  var storyFolder = storyFolders.next();

  return storyCacheFindFile_(storyFolder, parts[2]);
}
