// Supabase Edge Function: public-calls
// =========================================================================
// Zwraca opublikowane nabory jako gotowy JSON, z agresywnym cache.
// Dlaczego nie prosto z REST? - bo to daje:
//   1. Latwy CORS (Access-Control-Allow-Origin: https://inwestycjepomorze.pl)
//   2. Edge cache CDN (do 5 min) -> mniej query do bazy, szybciej dla uzytkownika
//   3. Mozliwosc przekszztalcania payloadu bez zmiany RLS na bazie.
//
// Deploy:
//   supabase functions deploy public-calls --no-verify-jwt
//
// Endpoint:
//   GET https://<project>.supabase.co/functions/v1/public-calls
//
// Parametry query:
//   ?status=open|upcoming|closed|all
//   ?program=feng|kpo|fe-pomorze|...
//   ?limit=200
// =========================================================================

import { createClient } from "jsr:@supabase/supabase-js@2";

const ALLOWED_ORIGINS = new Set([
  "https://inwestycjepomorze.pl",
  "https://www.inwestycjepomorze.pl",
  "http://localhost:8080", // dev
  "http://localhost:3000",
]);

function corsHeaders(origin: string | null): Record<string, string> {
  const allowed = origin && ALLOWED_ORIGINS.has(origin) ? origin : "https://inwestycjepomorze.pl";
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, apikey, authorization",
    "Vary": "Origin",
  };
}

Deno.serve(async (req) => {
  const origin = req.headers.get("origin");
  const cors = corsHeaders(origin);

  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: cors });
  }
  if (req.method !== "GET") {
    return new Response("Method Not Allowed", { status: 405, headers: cors });
  }

  const url = new URL(req.url);
  const status = url.searchParams.get("status") ?? "all";
  const program = url.searchParams.get("program");
  const limit = Math.min(parseInt(url.searchParams.get("limit") ?? "200", 10) || 200, 500);

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { auth: { persistSession: false } },
  );

  let query = supabase
    .from("published_calls_v")
    .select("*")
    .order("deadline", { ascending: true, nullsFirst: false })
    .order("published_at", { ascending: false })
    .limit(limit);

  const today = new Date().toISOString().slice(0, 10);
  if (status === "open") {
    query = query.gte("deadline", today);
  } else if (status === "closed") {
    query = query.lt("deadline", today);
  } else if (status === "upcoming") {
    query = query.is("deadline", null);
  }

  if (program) {
    query = query.contains("tags", [program]);
  }

  const { data, error } = await query;
  if (error) {
    console.error("public-calls error", error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...cors, "Content-Type": "application/json" },
    });
  }

  return new Response(JSON.stringify({ count: data?.length ?? 0, calls: data ?? [] }), {
    status: 200,
    headers: {
      ...cors,
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600",
    },
  });
});
