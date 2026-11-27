/**
 * TÀNG THƯ — Trigger the existing Partial Build workflow after a changed Refresh.
 *
 * Reuses githubToken_() and githubHeaders_() from apps-script/Code.gs.
 * The existing partial-build queue remains the single source of truth.
 */
function dispatchPartialBuildWorkflow_(info) {
  var token = githubToken_();
  var url = 'https://api.github.com/repos/Zenkjt/tangthu-opds/dispatches';
  var payload = {
    event_type: 'partial_build_requested',
    client_payload: {
      source: 'tangthu-refresh',
      shelf_id: String((info || {}).shelf_id || ''),
      detected_at: new Date().toISOString()
    }
  };
  var delays = [1000, 2000, 4000];
  var lastError = null;

  for (var attempt = 0; attempt < 4; attempt++) {
    try {
      var response = UrlFetchApp.fetch(url, {
        method: 'post',
        muteHttpExceptions: true,
        contentType: 'application/json',
        payload: JSON.stringify(payload),
        headers: githubHeaders_(token)
      });

      var status = response.getResponseCode();
      if (status === 204) {
        Logger.log(
          'TÀNG THƯ: Partial Build dispatched after changed Refresh. shelf=' +
          String((info || {}).shelf_id || '')
        );
        return {ok: true, dispatched: true};
      }

      var body = response.getContentText();
      lastError = new Error(
        'GitHub Partial Build dispatch thất bại: HTTP ' + status + ' ' + body
      );

      if (status !== 408 && status !== 429 && status < 500) {
        throw lastError;
      }
    } catch (err) {
      lastError = err;
      if (attempt === 3) break;
    }

    if (attempt < 3) Utilities.sleep(delays[attempt]);
  }

  Logger.log('TÀNG THƯ: Partial Build dispatch failed; queue is retained. ' + String(lastError));
  throw lastError || new Error('Không thể kích hoạt Partial Build.');
}
