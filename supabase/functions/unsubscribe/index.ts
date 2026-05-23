// Edge Function: unsubscribe
// =========================================================================
// Endpoint dla one-click unsubscribe z newslettera. Wymog RODO + dobre praktyki.
// URL w mailu: https://<project>.supabase.co/functions/v1/unsubscribe?token=...
//
// Po kliknieciu uzytkownik widzi potwierdzajacy ekran HTML i ma email
// oznaczony jako unsubscribed.
// =========================================================================

import { createClient } from "jsr:@supabase/supabase-js@2";

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const token = url.searchParams.get("token");

  if (!token) {
    return htmlResponse("<h1>Bledny link</h1><p>Brak tokenu wypisu.</p>", 400);
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );

  const { data, error } = await supabase
    .from("subscribers")
    .update({ unsubscribed_at: new Date().toISOString() })
    .eq("unsubscribe_token", token)
    .select("email")
    .single();

  if (error || !data) {
    return htmlResponse(
      `<h1>Niepoprawny token</h1>
       <p>Nie udalo sie wypisac. Mozliwe, ze juz jestes wypisany lub link wygasl.</p>
       <p><a href="https://inwestycjepomorze.pl">Wroc na strone glowna</a></p>`,
      404,
    );
  }

  return htmlResponse(
    `<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <title>Wypisany - InwestycjePomorze.pl</title>
  <meta http-equiv="refresh" content="5;url=https://inwestycjepomorze.pl">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 80px auto; padding: 24px; text-align: center; color: #1a1a1a; }
    .ok { background: #d1fae5; border: 1px solid #10b981; padding: 24px; border-radius: 12px; }
    .ok h1 { margin: 0 0 12px; color: #065f46; }
    a { color: #0a4d8c; }
  </style>
</head>
<body>
  <div class="ok">
    <h1>Wypisany ze subskrypcji</h1>
    <p>Adres <strong>${escapeHtml(data.email)}</strong> zostal usuniety z naszej listy mailingowej.</p>
    <p>Nie bedziemy juz wysylac do Ciebie newsletterow.</p>
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
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
