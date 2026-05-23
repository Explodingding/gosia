// Edge Function: subscribe
// =========================================================================
// Endpoint do zapisu na newsletter klientow z formularza inwestycjepomorze.pl.
// Wysyla mail z linkiem potwierdzajacym (double opt-in - wymog RODO best practice).
// =========================================================================

import { createClient } from "jsr:@supabase/supabase-js@2";

const ALLOWED_ORIGINS = new Set([
  "https://inwestycjepomorze.pl",
  "https://www.inwestycjepomorze.pl",
  "http://localhost:8080",
  "http://localhost:3000",
]);

function corsHeaders(origin: string | null): Record<string, string> {
  const allowed = origin && ALLOWED_ORIGINS.has(origin) ? origin : "https://inwestycjepomorze.pl";
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  };
}

interface SubscribePayload {
  email: string;
  name?: string;
  company?: string;
  interests?: string[]; // ["fundusze_ue", "kpo", "programy_regionalne"]
  consent: boolean;
}

const VALID_INTERESTS = new Set(["fundusze_ue", "kpo", "programy_regionalne"]);

Deno.serve(async (req) => {
  const origin = req.headers.get("origin");
  const cors = corsHeaders(origin);

  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: cors });
  }
  if (req.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405, headers: cors });
  }

  let payload: SubscribePayload;
  try {
    payload = await req.json();
  } catch {
    return json({ error: "Invalid JSON" }, 400, cors);
  }

  const email = String(payload.email || "").trim().toLowerCase();
  const name = String(payload.name || "").trim() || null;
  const company = String(payload.company || "").trim() || null;
  const consent = Boolean(payload.consent);
  const interests = Array.isArray(payload.interests)
    ? payload.interests.filter((i) => VALID_INTERESTS.has(i))
    : [];

  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return json({ error: "Niepoprawny adres email" }, 400, cors);
  }
  if (!consent) {
    return json({ error: "Wymagana zgoda RODO" }, 400, cors);
  }
  if (interests.length === 0) {
    return json({ error: "Wybierz przynajmniej jedna kategorie zainteresowan" }, 400, cors);
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );

  // Upsert zachowuje istniejace consent_at + unsubscribe_token jesli juz istnial.
  const { data, error } = await supabase
    .from("subscribers")
    .upsert(
      {
        email,
        name,
        company,
        interest_ue: interests.includes("fundusze_ue"),
        interest_kpo: interests.includes("kpo"),
        interest_regional: interests.includes("programy_regionalne"),
        unsubscribed_at: null,
      },
      { onConflict: "email" },
    )
    .select()
    .single();

  if (error || !data) {
    console.error("subscribe error", error);
    return json({ error: "Blad zapisu - sprobuj ponownie" }, 500, cors);
  }

  // Wyslij mail z potwierdzeniem (double opt-in)
  const supaUrl = Deno.env.get("SUPABASE_URL")!;
  const confirmUrl = `${supaUrl}/functions/v1/confirm?token=${data.unsubscribe_token}&email=${encodeURIComponent(email)}`;

  await sendConfirmEmail({
    to: email,
    name,
    confirmUrl,
  });

  return json({ ok: true, message: "Sprawdz skrzynke i potwierdz subskrypcje" }, 200, cors);
});

function json(body: unknown, status: number, cors: Record<string, string>) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, "Content-Type": "application/json; charset=utf-8" },
  });
}

async function sendConfirmEmail(args: { to: string; name: string | null; confirmUrl: string }) {
  const resendKey = Deno.env.get("RESEND_API_KEY");
  const from = Deno.env.get("MAIL_FROM") || "Newsletter InwestycjePomorze <newsletter@inwestycjepomorze.pl>";
  if (!resendKey) {
    console.warn("Brak RESEND_API_KEY - nie wysylam maila potwierdzajacego");
    return;
  }

  const greeting = args.name ? `Dzien dobry, ${args.name}!` : "Dzien dobry!";
  const html = `
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
      <h2 style="color: #0a4d8c;">${greeting}</h2>
      <p>Dziekujemy za zapisanie sie do newslettera <strong>InwestycjePomorze.pl</strong>.</p>
      <p>Aby aktywowac subskrypcje i otrzymywac cotygodniowe podsumowania nowych naborow funduszy unijnych, kliknij ponizszy przycisk:</p>
      <p style="text-align: center; margin: 32px 0;">
        <a href="${args.confirmUrl}" style="background: #0a4d8c; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 600;">Potwierdz subskrypcje</a>
      </p>
      <p style="font-size: 12px; color: #666;">Jesli to nie Ty zapisales sie do newslettera, po prostu zignoruj ten mail.</p>
      <hr>
      <p style="font-size: 12px; color: #999;">InwestycjePomorze.pl &middot; Banino, gmina Zukowo &middot; <a href="https://inwestycjepomorze.pl/polityka-prywatnosci" style="color: #999;">Polityka prywatnosci</a></p>
    </div>
  `;
  const text = `${greeting}\n\nDziekujemy za zapis do newslettera InwestycjePomorze.pl.\n\nAby potwierdzic, kliknij: ${args.confirmUrl}\n\nJesli to nie Ty - zignoruj.`;

  await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${resendKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from,
      to: [args.to],
      subject: "Potwierdz subskrypcje - InwestycjePomorze.pl",
      html,
      text,
    }),
  });
}
