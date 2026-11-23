/**
 * TÀNG THƯ — Export global book inventory to TTlist.xlsx.
 * Called only through the existing doPost action router in Code.gs.
 */
function exportInventory_(body) {
  var props = PropertiesService.getScriptProperties();
  var expectedToken = String(props.getProperty('TANGTHU_UPLOAD_TOKEN') || '');
  if (!expectedToken || String(body.token || '') !== expectedToken) {
    return { ok: false, error: 'Unauthorized inventory export request.' };
  }

  var folderId = String(body.folder_id || '').trim();
  if (!folderId) return { ok: false, error: 'Missing target shelf folder.' };

  var config = readConfig_();
  var registered = null;
  for (var i = 0; i < config.branches.length; i++) {
    var candidate = config.branches[i];
    if (String(candidate.root_folder_id) === folderId && candidate.enabled !== false) {
      registered = candidate;
      break;
    }
  }
  if (!registered) return { ok: false, error: 'Target folder is not an active registered Tàng Thư shelf.' };

  var targetFolder;
  try {
    targetFolder = DriveApp.getFolderById(folderId);
  } catch (err) {
    return { ok: false, error: 'Apps Script cannot write to this shelf: ' + String(err) };
  }

  var catalogResponse = UrlFetchApp.fetch(
    'https://tangthu.pages.dev/catalog.json?inventory=' + Date.now(),
    { muteHttpExceptions: true, followRedirects: true, headers: { 'Cache-Control': 'no-cache' } }
  );
  if (catalogResponse.getResponseCode() !== 200) {
    return { ok: false, error: 'Không đọc được catalog.json: HTTP ' + catalogResponse.getResponseCode() };
  }

  var catalog;
  try {
    catalog = JSON.parse(catalogResponse.getContentText());
  } catch (err) {
    return { ok: false, error: 'catalog.json không phải JSON hợp lệ.' };
  }
  if (!catalog || Number(catalog.version) !== 2 || !Array.isArray(catalog.branches) || !catalog.branches.length) {
    return { ok: false, error: 'catalog manifest không hợp lệ hoặc chưa được cập nhật sang version 2.' };
  }

  // Reuse the static per-shelf search index. No directory shards are expanded.
  var expandedBranches = [];
  var catalogBase = 'https://tangthu.pages.dev/';
  for (var bi = 0; bi < catalog.branches.length; bi++) {
    var shelf = catalog.branches[bi];
    if (shelf.status === 'suspended' || shelf.status === 'disabled') continue;
    var paths = Array.isArray(shelf.search_shards) ? shelf.search_shards : [];
    var files = [];
    for (var ji = 0; ji < paths.length; ji += 50) {
      var batch = paths.slice(ji, ji + 50);
      var requests = batch.map(function (path) {
        return { url: catalogBase + path, muteHttpExceptions: true, followRedirects: true };
      });
      var responses;
      try { responses = UrlFetchApp.fetchAll(requests); }
      catch (err) { return { ok: false, error: 'Không tải được search index của tủ ' + shelf.name + ': ' + String(err) }; }
      for (var ri = 0; ri < responses.length; ri++) {
        if (responses[ri].getResponseCode() !== 200) {
          return { ok: false, error: 'Search index lỗi ở tủ ' + shelf.name + ': HTTP ' + responses[ri].getResponseCode() };
        }
        var shard;
        try { shard = JSON.parse(responses[ri].getContentText()); }
        catch (err) { return { ok: false, error: 'Search index không phải JSON hợp lệ ở tủ ' + shelf.name }; }
        if (shard.branch_id !== shelf.id) return { ok: false, error: 'Search index không khớp tủ ' + shelf.name };
        files = files.concat(shard.items || []);
      }
    }
    expandedBranches.push({
      id: shelf.id, name: shelf.name, root_folder_id: shelf.root_folder_id,
      shelf_no: shelf.shelf_no, status: shelf.status, files: files
    });
  }
  catalog.branches = expandedBranches;

  var allowed = {
    epub: true, mobi: true, azw3: true, cbz: true, lit: true, chm: true,
    prc: true, pdf: true, zip: true, doc: true, docx: true, txt: true, md: true
  };
  var configById = {};
  config.branches.forEach(function (item) { configById[String(item.id)] = item; });

  var allRows = [];
  var shelfRows = [];
  var totalBytes = 0;

  catalog.branches.forEach(function (shelf) {
    var files = Array.isArray(shelf.files) ? shelf.files : [];
    var count = 0;
    var bytes = 0;
    files.forEach(function (file) {
      if (!file || file.folder || !file.id) return;
      var name = String(file.name || '');
      var match = /\.([^.]+)$/.exec(name);
      var extension = match ? match[1].toLowerCase() : '';
      if (!allowed[extension]) return;

      var folderPath = String(file.path || '/');
      var size = Math.max(0, Number(file.size) || 0);
      var configuredShelf = configById[String(shelf.id)] || {};
      var shelfNo = Number(shelf.shelf_no || configuredShelf.shelf_no || 0);
      var shelfName = String(shelf.name || shelf.display_name || '');

      allRows.push([
        inventorySafeText_(name),
        extension.toUpperCase(),
        size,
        shelfNo,
        inventorySafeText_(shelfName),
        folderPath === '/' ? 'Thư mục gốc' : 'Thư mục con',
        inventorySafeText_(folderPath)
      ]);
      count++;
      bytes += size;
    });

    shelfRows.push([
      Number(shelf.shelf_no || (configById[String(shelf.id)] || {}).shelf_no || 0),
      inventorySafeText_(String(shelf.name || shelf.display_name || '')),
      count,
      bytes
    ]);
    totalBytes += bytes;
  });

  if (!allRows.length) return { ok: false, error: 'Không tìm thấy file sách thuộc 13 định dạng được hỗ trợ.' };

  allRows.sort(function (a, b) {
    return (Number(a[3]) - Number(b[3])) ||
      String(a[4]).localeCompare(String(b[4]), 'vi') ||
      String(a[6]).localeCompare(String(b[6]), 'vi') ||
      String(a[0]).localeCompare(String(b[0]), 'vi');
  });
  shelfRows.sort(function (a, b) { return Number(a[0]) - Number(b[0]); });

  var spreadsheet = SpreadsheetApp.create('TTlist-export-' + Date.now());
  var spreadsheetId = spreadsheet.getId();
  try {
    var books = spreadsheet.getSheets()[0];
    books.setName('Books');
    var bookHeaders = [[
      'Tên file', 'Định dạng', 'Dung lượng (byte)', 'Số tủ',
      'Tên tủ', 'Vị trí', 'Đường dẫn thư mục'
    ]];
    books.getRange(1, 1, 1, bookHeaders[0].length).setValues(bookHeaders);
    books.getRange(1, 1, 1, bookHeaders[0].length).setFontWeight('bold');
    books.setFrozenRows(1);
    books.getRange(2, 1, allRows.length, 7).setValues(allRows);
    books.getRange(2, 3, allRows.length, 1).setNumberFormat('#,##0');
    books.getRange(2, 4, allRows.length, 1).setNumberFormat('0');
    books.getRange(1, 1, allRows.length + 1, 7).createFilter();
    books.setColumnWidth(1, 360);
    books.setColumnWidth(2, 95);
    books.setColumnWidth(3, 145);
    books.setColumnWidth(4, 75);
    books.setColumnWidth(5, 220);
    books.setColumnWidth(6, 115);
    books.setColumnWidth(7, 300);

    var shelves = spreadsheet.insertSheet('Shelves');
    var shelfHeaders = [['Số tủ', 'Tên tủ', 'Số file sách', 'Tổng dung lượng (byte)']];
    shelves.getRange(1, 1, 1, 4).setValues(shelfHeaders).setFontWeight('bold');
    if (shelfRows.length) shelves.getRange(2, 1, shelfRows.length, 4).setValues(shelfRows);
    shelves.getRange(2, 4, Math.max(1, shelfRows.length), 1).setNumberFormat('#,##0');
    shelves.setFrozenRows(1);
    shelves.getRange(1, 1, shelfRows.length + 1, 4).createFilter();
    shelves.setColumnWidth(1, 75);
    shelves.setColumnWidth(2, 260);
    shelves.setColumnWidth(3, 120);
    shelves.setColumnWidth(4, 190);

    SpreadsheetApp.flush();
    var xlsxBlob = Drive.Files.export(
      spreadsheetId,
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    );
    xlsxBlob.setName('TTlist.xlsx');

    var existing = targetFolder.getFilesByName('TTlist.xlsx');
    var savedFile;
    if (existing.hasNext()) {
      savedFile = existing.next();
      if (existing.hasNext()) {
        return { ok: false, error: 'Có nhiều file TTlist.xlsx trong thư mục đích; hệ thống không ghi đè file không xác định.' };
      }
      Drive.Files.update(
        { name: 'TTlist.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
        savedFile.getId(),
        xlsxBlob,
        { supportsAllDrives: true }
      );
    } else {
      savedFile = targetFolder.createFile(xlsxBlob);
    }

    return {
      ok: true,
      filename: 'TTlist.xlsx',
      file_id: savedFile.getId(),
      book_count: allRows.length,
      shelf_count: shelfRows.length,
      total_size_bytes: totalBytes
    };
  } catch (err) {
    return { ok: false, error: 'Không tạo được TTlist.xlsx: ' + String(err) };
  } finally {
    try { DriveApp.getFileById(spreadsheetId).setTrashed(true); } catch (cleanupError) {}
  }
}

function inventorySafeText_(value) {
  var text = String(value == null ? '' : value);
  return /^[=+\-@]/.test(text) ? "'" + text : text;
}
