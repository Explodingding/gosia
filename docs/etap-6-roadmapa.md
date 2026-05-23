# Etap 6 - Opcjonalne rozszerzenia (roadmapa)

> Ten etap jest **opcjonalny**. MVP (Etapy 0-3) i pelna integracja biznesowa (Etapy 4-5) dzialaja samodzielnie. Tu sa pomysly, ktore mozna dodac, gdy MVP juz dziala stabilnie i widac konkretna potrzebe.

## 6.1 RAG dla Asystenta Dotacji AI na stronie

### Sytuacja aktualna

Strona inwestycjepomorze.pl ma juz wbudowanego "Asystenta Dotacji AI powered by Claude". Aktualnie odpowiada na podstawie wiedzy modelu Claude (statyczna, do daty cutoffu).

### Cel

Asystent ma odpowiadac w oparciu o **aktualna baze naborow** w Supabase. Przyklady pytan, na ktore zacznie odpowiadac konkretnie:

- "Jakie nabory KPO sa otwarte dla MSP w wojewodztwie pomorskim?"
- "Czy jest jakis nabor na fotowoltaike z deadlinem w lipcu?"
- "Pokaz mi nabory na B+R z dofinansowaniem powyzej 1 mln zl."

### Implementacja

**Wariant A - Function calling (rekomendowany)**:

Claude/GPT dostaje narzedzia (tools/functions):
- `search_calls(query, status, program, region, beneficiary, max_amount, deadline_before)` -> wraca lista naborow z bazy
- `get_call_details(call_id)` -> pelne szczegoly konkretnego naboru

Model sam decyduje, kiedy zawolac narzedzie. Brak embeddings/wektorow - wystarczy SQL.

**Plik**: `supabase/functions/asystent-naborow/index.ts`

```typescript
// Pseudokod
Deno.serve(async (req) => {
  const { messages } = await req.json();
  const tools = [
    {
      name: "search_calls",
      description: "Wyszuka opublikowane nabory wedlug kryteriow",
      parameters: { /* JSON schema z polami */ }
    },
    { name: "get_call_details", parameters: { /* ... */ } }
  ];

  const response = await callClaude({ messages, tools, system: SYSTEM_PROMPT });

  if (response.tool_use) {
    const toolResult = await executeTool(response.tool_use); // SELECT z bazy
    // re-call Claude z tool result
  }

  return response.text;
});
```

**Wariant B - Pelne RAG z embeddings**:

Bardziej skomplikowane, ale lepsze gdy mamy >1000 naborow.

1. Po enrichment LLM: dodatkowo zapisujemy embedding (OpenAI `text-embedding-3-small`, 1536 wymiarow) do kolumny `calls.embedding` typu `vector(1536)` (rozszerzenie pgvector).
2. Asystent: na pytanie usera generujemy embedding pytania, robimy `<=>` (cosine similarity) z `calls.embedding`, pobieramy top-5, dorzucamy do prompta.

Koszt: ~$0.02/1M tokenow embeddingu, marginalny przy ~50 naborach dziennie.

### Czas implementacji

- Wariant A: 1-2 sesje pracy (4-6 h).
- Wariant B: 2-3 sesje pracy (6-12 h).

---

## 6.2 Telegram bot dla Malgorzaty

### Cel

Ad-hoc pytania bez otwierania arkusza/maila. Przyklady:

- "Pokaz nabory FENG z deadlinem do konca miesiaca"
- "Co jest nowego od poniedzialku?"
- "Streszcz mi nabor #1234"

### Implementacja

1. **BotFather** -> stworzenie bota -> token.
2. **Edge Function `telegram-webhook`** w Supabase:
   - Telegram POST-uje update -> function loguje wiadomosc.
   - Routing prostych komend (`/start`, `/today`, `/search FENG`).
   - Skomplikowane pytania -> przepuszczamy przez ten sam Asystent (6.1) z function calling.
3. **Whitelist** chat_id - bot odpowiada tylko Malgorzacie + ewentualnie zespolowi.
4. Cron `daily-digest` w Telegram - opcjonalny.

**Plik**: `supabase/functions/telegram-webhook/index.ts`

### Czas implementacji

1 sesja pracy (~3-4 h), gdy 6.1 jest juz wdrozony.

---

## 6.3 Dashboard analityczny

### Cel

Statystyki dla Malgorzaty:

- Ile naborow miesiecznie / kwartalnie / rocznie.
- Top programow wedlug liczby naborow.
- Sredni profile_match_score.
- Ile naborow opublikowanych vs odrzuconych.
- Ile maili i otwarc newslettera (jesli wlaczony tracking).
- Top zrodel po liczbie nowych ogloszen / niezawodnosci.

### Implementacja

**Wariant A - Supabase Studio + zapisane queries (najszybsze)**:

W Supabase Dashboard -> **SQL Editor** -> zapisz queries jako "Saved":

```sql
-- Nabory miesiecznie
select to_char(created_at, 'YYYY-MM') as miesiac, count(*) as nabory
from calls
group by 1 order by 1 desc;

-- Top programow
select program, count(*) as ile, avg(profile_match_score) as avg_match
from calls where program is not null
group by program order by ile desc;
```

**Wariant B - Metabase (rekomendowane jesli chce sie dashboard wizualny)**:

1. Hostowanie: darmowy plan Metabase Cloud (lub Docker na malym VPS - 20 zl/mies).
2. Polacz z Supabase (Postgres connection string z `SUPABASE_DB_PASSWORD`).
3. Stworz dashboardy: "Pulpit naborow", "Analiza zrodel", "Wydajnosc filtrowania".

**Wariant C - Wlasny dashboard Next.js**:

Najwiekszy nakład, ale daje pelna kontrole + mozna podpiac do panelu Malgorzaty z autoryzacja.

### Czas implementacji

- Wariant A: 1 h (zapisanie 10 query).
- Wariant B: 2-4 h.
- Wariant C: 2-3 sesje pracy.

---

## 6.4 Integracja z CRM klientek

Jesli InwestycjePomorze.pl uzywa CRM (np. Pipedrive, HubSpot, Bitrix24), warto:

- **Auto-tworzyc deale** dla potencjalnych klientow zapisanych w newsletterze.
- **Notify Malgorzata** na Slack/Discord, gdy nowy zapisany jest z firmy duzej (>250 osob).
- **Tag klientow** wg zainteresowan z preferencji newsletterowych.

To wymaga zdefiniowania, jaki jest aktualny CRM - mozemy uzgodnic.

---

## 6.5 Smart filter LLM (filtruj zamiast tylko streszczac)

### Sytuacja aktualna

Aktualnie LLM tylko **ocenia dopasowanie (0-100)** i streszcza. Wszystkie nowe nabory laduja w bazie ze statusem `draft` i Malgorzata recznie zaznacza `publikuj`/`odrzuc`.

### Mozliwa zmiana

Po kilku miesiacach uzytkowania, kiedy bedzie historia decyzji Malgorzaty, mozemy:

1. **Auto-publikowac** nabory z `profile_match_score >= 85` (ufamy LLM).
2. **Auto-odrzucac** te z `profile_match_score < 20`.
3. **Manualne** zostawiamy tylko `20-85`.

Albo nawet:

4. **Fine-tune profilu**: na podstawie tego, ktore nabory Malgorzata akceptuje vs odrzuca, **automatycznie aktualizujemy** `profile.md` (lub trzymamy historie decyzji jako few-shot examples w prompcie LLM-a).

### Czas implementacji

- Auto-publikacja po score: 30 min (jeden if w `main.py`).
- Few-shot z historii decyzji: 1-2 h.
- Pelny fine-tuning OpenAI: 4-6 h + ~$5-15 jednorazowo na fine-tune.

---

## 6.6 Web crawler dla nowych zrodel

Kiedy Malgorzata bedzie chciala dodac nowe zrodlo, ale nie zna konkretnego URL - moze podac topic:

- "Znajdz mi portale z dotacjami dla branzy turystycznej."
- "Jakie organizacje pozarzadowe maja swoje konkursy?"

Bot z Tavily/Perplexity API wraca z lista kandydatow + ocena, czy strona ma stabilna liste naborow.

Czas implementacji: 1-2 sesje.

---

## Priorytetyzacja

Sugerowana kolejnosc po MVP (Etapy 0-5):

1. **Wariant A 6.1** (Asystent z function calling) - najwiekszy efekt biznesowy dla strony i klientow.
2. **6.5 Auto-publikacja** - oszczedza Malgorzacie czas codziennie.
3. **6.3 Wariant A** (Saved queries Supabase) - szybkie statystyki.
4. **6.2 Telegram bot** - wygoda Malgorzaty.
5. **6.3 Wariant B** (Metabase) - jak juz duzo danych.

Zalecenie: **odczekaj 1-2 miesiace** na MVP w produkcji, zbierz feedback Malgorzaty, dopiero wtedy decyduj co z Etapu 6 ma sens.
