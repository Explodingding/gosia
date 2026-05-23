// Edge Function: confirm
// =========================================================================
// Endpoint dla double opt-in - aktywuje subskrypcje po kliknieciu w mailu.
// =========================================================================

import { createClient } from "jsr:@supabase/supabase-js@2";

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const token = url.searchParams.get("token");
  const email = url.searchParams.get("email");

  if (!token || !email) {
    return htmlResponse("<h1>Bledny link</h1>", 400);
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );

  const { data, error } = await supabase
    .from("subscribers")
    .update({ confirmed_at: new Date().toISOString() })
    .eq("unsubscribe_token", token)
    .eq("email", email.toLowerCase())
    .select("email")
    .single();

  if (error || !data) {
    return htmlResponse(
      `<h1>Niepoprawny link</h1>
       <p>Nie udalo sie potwierdzic subskrypcji. Sprobuj zapisac sie ponownie.</p>`,
      404,
    );
  }

  return htmlResponse(
    `<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <title>Subskrypcja potwierdzona</title>
  <meta http-equiv="refresh" content="5;url=https://inwestycjepomorze.pl">
  <style>
    body { font-family: sans-serif; max-width: 600px; margin: 80px auto; padding: 24px; text-align: center; color: #1a1a1a; }
    .ok { background: #d1fae5; border: 1px solid #10b981; padding: 24px; border-radius: 12px; }
    .ok h1 { margin: 0 0 12px; color: #065f46; }
  </style>
</head>
<body>
  <div class="ok">
    <h1>Subskrypcja potwierdzona</h1>
    <p>Adres <strong>${escapeHtml(data.email)}</strong> jest aktywny.</p>
    <p>W kazdy piatek otrzymasz cotygodniowe podsumowanie nowych naborow pasujacych do Twoich preferencji.</p>
  </div>
  <p style="margin-top: 24px;">
    Za 5 sekund nastapi przekierowanie na <a href="https://inwestycjepomorze.pl">strone glowna</a>.
  </p>
</body>
</html>`,
    200,
  );
});

function htmlResponse(html: string, status: number) {
  return new Response(html, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

function escapeHtml(s: string): string {
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
