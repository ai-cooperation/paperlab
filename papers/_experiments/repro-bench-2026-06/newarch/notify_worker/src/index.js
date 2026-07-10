// Paper Lab completion notifier: HTTP -> Cloudflare Email Workers send_email
// binding (no SMTP). Destination is pinned by the binding to the account
// owner's verified Email Routing address. Bearer-token protected.
import { EmailMessage } from "cloudflare:email";

function rawMime(from, to, subject, text) {
  const date = new Date().toUTCString();
  // RFC 5322 minimal text/plain message; subject kept ASCII-safe by the caller.
  return [
    `From: Paper Lab <${from}>`,
    `To: <${to}>`,
    `Subject: ${subject.replace(/[\r\n]/g, " ").slice(0, 200)}`,
    `Date: ${date}`,
    `Message-ID: <${crypto.randomUUID()}@cooperation.tw>`,
    "MIME-Version: 1.0",
    'Content-Type: text/plain; charset="utf-8"',
    "Content-Transfer-Encoding: 8bit",
    "",
    text,
  ].join("\r\n");
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") return new Response("POST only", { status: 405 });
    const auth = request.headers.get("Authorization") || "";
    if (auth !== `Bearer ${env.NOTIFY_TOKEN}`) return new Response("unauthorized", { status: 401 });
    let body;
    try { body = await request.json(); } catch { return new Response("bad json", { status: 400 }); }
    const subject = String(body.subject || "Paper Lab notification");
    const text = String(body.text || "");
    const from = "notify@cooperation.tw";
    const to = "alan.chen75@gmail.com"; // pinned by the send_email binding
    try {
      await env.NOTIFY.send(new EmailMessage(from, to, rawMime(from, to, subject, text)));
      return Response.json({ status: "sent", to });
    } catch (err) {
      return Response.json({ status: "failed", error: String(err).slice(0, 300) }, { status: 502 });
    }
  },
};
