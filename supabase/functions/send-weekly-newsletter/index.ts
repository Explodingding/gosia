// Edge Function: send-weekly-newsletter
// =========================================================================
// Tygodniowy newsletter dla potwierdzonych subskrybentow. Segmentowany po
// preferencjach (Fundusze UE / KPO / Programy regionalne).
//
// Uruchamiane cron-em z Supabase Schedules:
//   piatek 08:00 Europe/Warsaw (czyli 06:00/07:00 UTC w zaleznosci od DST)
//
// Mapa segmentow -> tagi naborow:
//   fundusze_ue        -> feng, fe-pomorze, rpo, kpo (czesc unijna)
//   kpo                -> kpo, kpo-cyfryzacja, kpo-zielona, kpo-innowacje
//   programy_regionalne -> fe-pomorze, rpo
// =========================================================================

import { createClient } from "jsr:@supabase/supabase-js@2";

const SEGMENT_TAGS: Record<string, string[]> = {
  fundusze_ue: ["feng", "fe-pomorze", "rpo"],
  kpo: ["kpo", "kpo-cyfryzacja", "kpo-zielona", "kpo-innowacje"],
  programy_regionalne: ["fe-pomorze", "rpo"],
};

interface Subscriber {
  id: string;
  email: string;
  name: string | null;
  interest_ue: boolean;
  interest_kpo: boolean;
  interest_regional: boolean;
  unsubscribe_token: string;
  confirmed_at: string | null;
}

interface PublishedCall {
  id: string;
  title: string;
  url: string;
  deadline: string | null;
  region: string | null;
  beneficiary: string | null;
  program: string | null;
  amount_min: number | null;
  amount_max: number | null;
  summary: string | null;
  published_at: string;
  source_name: string | null;
  tags: string[];
}

Deno.serve(async (req) => {
  // Wewnetrzny endpoint - chronimy prostym shared secret w naglowku
  const cronSecret = Deno.env.get("CRON_SECRET");
  if (cronSecret && req.headers.get("x-cron-secret") !== cronSecret) {
    return new Response("Unauthorized", { status: 401 });
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );

  // 1. Pobierz potwierdzonych aktywnych subskrybentow
  const { data: subs, error: subsErr } = await supabase
    .from("subscribers")
    .select("*")
    .not("confirmed_at", "is", null)
    .is("unsubscribed_at", null);

  if (subsErr || !subs) {
    console.error("subscribers error", subsErr);
    return jsonRes({ error: "Nie udalo sie pobrac subskrybentow" }, 500);
  }

  // 2. Pobierz published calls z ostatnich 7 dni
  const since = new Date();
  since.setDate(since.getDate() - 7);
  const { data: calls, error: callsErr } = await supabase
    .from("published_calls_v")
    .select("*")
    .gte("published_at", since.toISOString())
    .limit(200);

  if (callsErr) {
    console.error("calls error", callsErr);
    return jsonRes({ error: "Nie udalo sie pobrac naborow" }, 500);
  }

  if (!calls || calls.length === 0) {
    console.log("Brak nowych naborow w ostatnim tygodniu - pomijam wysylke");
    return jsonRes({ ok: true, sent: 0, skipped_reason: "no_new_calls" });
  }

  // 3. Dla kazdego subskrybenta wybierz segmenty i wyslij
  const baseUrl = Deno.env.get("PUBLIC_BASE_URL") || "https://inwestycjepomorze.pl";
  const supaUrl = Deno.env.get("SUPABASE_URL")!;
  let sent = 0;
  let failed = 0;

  for (const sub of subs as Subscriber[]) {
    const subTags = collectSubscriberTags(sub);
    if (subTags.size === 0) continue;

    const matched = (calls as PublishedCall[]).filter((c) =>
      (c.tags || []).some((t) => subTags.has(t)),
    );
    if (matched.length === 0) continue;

    const ok = await sendNewsletterEmail({
      sub,
      calls: matched.slice(0, 10),
      totalThisWeek: matched.length,
      baseUrl,
      unsubscribeUrl: `${supaUrl}/functions/v1/unsubscribe?token=${sub.unsubscribe_token}`,
    });
    if (ok) sent++;
    else failed++;
  }

  return jsonRes({ ok: true, sent, failed, total_subscribers: subs.length });
});

function jsonRes(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

function collectSubscriberTags(sub: Subscriber): Set<string> {
  const tags = new Set<string>();
  if (sub.interest_ue) SEGMENT_TAGS.fundusze_ue.forEach((t) => tags.add(t));
  if (sub.interest_kpo) SEGMENT_TAGS.kpo.forEach((t) => tags.add(t));
  if (sub.interest_regional) SEGMENT_TAGS.programy_regionalne.forEach((t) => tags.add(t));
  return tags;
}

async function sendNewsletterEmail(args: {
  sub: Subscriber;
  calls: PublishedCall[];
  totalThisWeek: number;
  baseUrl: string;
  unsubscribeUrl: string;
}): Promise<boolean> {
  const resendKey = Deno.env.get("RESEND_API_KEY");
  const from = Deno.env.get("MAIL_FROM_NEWSLETTER")
    || Deno.env.get("MAIL_FROM")
    || "Newsletter InwestycjePomorze <newsletter@inwestycjepomorze.pl>";
  if (!resendKey) {
    console.error("Brak RESEND_API_KEY");
    return false;
  }

  const greeting = args.sub.name ? `Dzien dobry, ${args.sub.name}` : "Dzien dobry";
  const subject = `${args.totalThisWeek} ${args.totalThisWeek === 1 ? "nowy nabor" : "nowych naborow"} dla Ciebie - ${weekLabel()}`;

  const callsHtml = args.calls.map((c) => {
    const deadline = c.deadline ? `Termin: <strong>${formatDate(c.deadline)}</strong>` : "";
    const amount = formatAmount(c.amount_min, c.amount_max);
    const region = c.region ? c.region : "";
    const meta = [c.program, region, deadline, amount].filter(Boolean).join(" &middot; ");
    return `
      <div style="border-left: 3px solid #0a4d8c; padding: 12px 16px; margin: 16px 0; background: #f8fafc;">
        <h3 style="margin: 0 0 6px; font-size: 16px;">
          <a href="${escapeHtml(c.url)}" style="color: #0a4d8c; text-decoration: none;">${escapeHtml(c.title)}</a>
        </h3>
        ${meta ? `<div style="font-size: 12px; color: #555; margin-bottom: 6px;">${meta}</div>` : ""}
        ${c.summary ? `<p style="margin: 0 0 8px; font-size: 14px; color: #333;">${escapeHtml(c.summary)}</p>` : ""}
        <a href="${escapeHtml(c.url)}" style="font-size: 12px; color: #0a4d8c;">Przeczytaj wiecej &rarr;</a>
      </div>
    `;
  }).join("");

  const html = `
<!doctype html>
<html lang="pl">
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 720px; margin: 0 auto; padding: 24px; color: #1a1a1a; background: #fafafa;">
  <div style="background: white; padding: 28px; border-radius: 12px;">
    <h1 style="color: #0a4d8c; margin: 0 0 8px;">${greeting},</h1>
    <p style="margin: 0 0 24px;">w ostatnim tygodniu pojawilo sie <strong>${args.totalThisWeek}</strong> nowych naborow pasujacych do Twoich preferencji.</p>
    ${callsHtml}
    ${args.totalThisWeek > args.calls.length ? `<p style="margin-top: 16px;"><a href="${args.baseUrl}/#fundusze">Zobacz wszystkie ${args.totalThisWeek} naborow na stronie &rarr;</a></p>` : ""}

    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0 16px;">
    <p style="font-size: 13px; color: #666;">
      <strong>Potrzebujesz pomocy w aplikowaniu?</strong>
      <a href="${args.baseUrl}/#kontakt" style="color: #0a4d8c;">Umow darmowa konsultacje</a>.
    </p>
    <p style="font-size: 11px; color: #999; margin-top: 24px;">
      Otrzymujesz ten mail, bo zapisales sie do newslettera InwestycjePomorze.pl.<br>
      Nie chcesz juz otrzymywac maili? <a href="${args.unsubscribeUrl}" style="color: #999;">Wypisz sie</a>.<br>
      InwestycjePomorze.pl &middot; Banino, gmina Zukowo &middot;
      <a href="${args.baseUrl}/polityka-prywatnosci" style="color: #999;">Polityka prywatnosci</a>
    </p>
  </div>
</body>
</html>`;

  const text = args.calls.map((c) =>
    `- ${c.title}\n  ${c.summary || ""}\n  ${c.url}\n`
  ).join("\n");

  try {
    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${resendKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from,
        to: [args.sub.email],
        subject,
        html,
        text,
        headers: {
          "List-Unsubscribe": `<${args.unsubscribeUrl}>`,
          "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
      }),
    });
    if (!res.ok) {
      console.error("Resend error", res.status, await res.text());
      return false;
    }
    return true;
  } catch (e) {
    console.error("send error", e);
    return false;
  }
}

function escapeHtml(s: string): string {
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function formatAmount(min: number | null, max: number | null): string {
  if (!min && !max) return "";
  const fmt = (v: number) => `${v.toLocaleString("pl-PL", { maximumFractionDigits: 0 })} PLN`;
  if (max && min && min !== max) return `${fmt(min)} - ${fmt(max)}`;
  if (max) return `do ${fmt(max)}`;
  if (min) return `od ${fmt(min)}`;
  return "";
}

function weekLabel(): string {
  const d = new Date();
  return d.toLocaleDateString("pl-PL", { day: "2-digit", month: "long" });
}
