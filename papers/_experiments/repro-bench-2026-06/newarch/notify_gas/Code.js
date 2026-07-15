// Paper Lab notify relay (Google Apps Script, free path).
// Chosen 2026-07-15 after Cloudflare Email Sending turned out to be
// Workers-Paid-only: MailApp on a consumer Gmail sends to arbitrary external
// recipients at no cost (~100 recipients/day quota).
//
// MUST be deployed under aicooperation.tw@gmail.com (MailApp sends as the
// script owner). Deploy as Web App: Execute as "Me", access "Anyone".
// GAS cannot read request headers, so auth is the token INSIDE the JSON body
// (unlike the Cloudflare paper-notify worker's Authorization header).
//
// Contract: POST {token, to, subject, text} -> {"status":"sent","to":...}
// Consumed by engine_v3/notify.py::_send_gas (NOTIFY_GAS_URL/NOTIFY_GAS_TOKEN).

var TOKEN = "REPLACE_WITH_NOTIFY_GAS_TOKEN"; // paste the real value when deploying; must equal NOTIFY_GAS_TOKEN on ac-2012. Never commit the real token.
var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function doPost(e) {
  var body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return json_({ status: "failed", error: "bad json" });
  }
  if (String(body.token || "") !== TOKEN) {
    return json_({ status: "failed", error: "unauthorized" });
  }
  var to = String(body.to || "").trim();
  var subject = String(body.subject || "Paper Lab notification").slice(0, 200);
  var text = String(body.text || "");
  if (!EMAIL_RE.test(to)) {
    return json_({ status: "failed", error: "invalid recipient" });
  }
  try {
    MailApp.sendEmail({ to: to, subject: subject, body: text, name: "Paper Lab" });
    return json_({ status: "sent", to: to, quota_left: MailApp.getRemainingDailyQuota() });
  } catch (err) {
    return json_({ status: "failed", error: String(err).slice(0, 300) });
  }
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}
