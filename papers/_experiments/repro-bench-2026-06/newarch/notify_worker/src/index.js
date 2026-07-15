// Paper Lab notifier: HTTP -> Cloudflare Email Service (transactional sending).
// Upgraded 2026-07-15 from the Email Routing send_email binding (recipient was
// pinned to the account owner's verified address; external users could never
// receive their completion email). The Email Service binding sends to the
// recipient in the payload; the from domain (cooperation.tw) must stay
// onboarded to Email Sending (npx wrangler email sending list).
// Bearer-token protected - this worker is not an open relay.
const FROM = { email: "notify@cooperation.tw", name: "Paper Lab" };
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default {
  async fetch(request, env) {
    if (request.method !== "POST") return new Response("POST only", { status: 405 });
    const auth = request.headers.get("Authorization") || "";
    if (auth !== `Bearer ${env.NOTIFY_TOKEN}`) return new Response("unauthorized", { status: 401 });
    let body;
    try { body = await request.json(); } catch { return new Response("bad json", { status: 400 }); }
    const to = String(body.to || "").trim();
    const subject = String(body.subject || "Paper Lab notification").slice(0, 200);
    const text = String(body.text || "");
    if (!EMAIL_RE.test(to)) {
      return Response.json({ status: "failed", error: "invalid recipient" }, { status: 400 });
    }
    try {
      const result = await env.EMAIL.send({ to, from: FROM, subject, text });
      return Response.json({ status: "sent", to, result });
    } catch (err) {
      return Response.json({ status: "failed", error: String(err).slice(0, 300) }, { status: 502 });
    }
  },
};
