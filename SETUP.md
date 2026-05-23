# Instrukcja przygotowania (Etap 0)

Ten dokument prowadzi przez wszystkie jednorazowe kroki, ktore trzeba wykonac PRZED pierwszym uruchomieniem agenta. Po zakonczeniu wszystko bedzie zautomatyzowane: codziennie o 6:00 UTC GitHub Actions uruchomi pipeline, a Malgorzata dostanie mail.

**Suma czasu: ~30-45 min** (jednorazowo).

---

## Krok 1. Konto GitHub i repo (5 min)

1. Jesli nie masz konta - zaloz na https://github.com/signup (darmowe).
2. Utworz **prywatne** repo o nazwie `nabory`:
   - https://github.com/new
   - Owner: Twoja nazwa uzytkownika
   - Repository name: `nabory`
   - Visibility: **Private** (wazne - bedzie zawieralo konfiguracje zrodel)
   - NIE inicjalizuj README ani .gitignore (mamy juz lokalnie)
3. Wypchnij lokalny katalog do GitHub:
   ```powershell
   cd c:\Users\SPCX\Desktop\nabory
   git init
   git add .
   git commit -m "Initial commit: agent naborow MVP"
   git branch -M main
   git remote add origin https://github.com/TWOJA_NAZWA/nabory.git
   git push -u origin main
   ```

---

## Krok 2. Projekt Supabase (10 min)

1. Wejdz na https://supabase.com i zaloz darmowe konto (GitHub login dziala).
2. Kliknij **New project**:
   - **Organization**: utworz lub wybierz
   - **Name**: `inwestycje-pomorze-naboru`
   - **Database password**: wygeneruj silne haslo i ZAPISZ (do `.env` jako `SUPABASE_DB_PASSWORD` opcjonalnie - nie jest potrzebne dla agenta, ale przyda sie do bezposredniego dostepu)
   - **Region**: `Central EU (Frankfurt)` (najblizej Polski)
   - **Pricing Plan**: Free
3. Poczekaj 1-2 min az projekt sie zainicjalizuje.
4. Po starcie projektu, w lewym menu wejdz w **SQL Editor** i wklej zawartosc pliku `supabase/migrations/0001_init.sql` z tego repo. Kliknij **Run**.
5. Wklej zawartosc `supabase/seed.sql` w SQL Editor i uruchom.
6. W lewym menu wejdz w **Project Settings -> API**. Skopiuj:
   - **Project URL** (np. `https://xxxxxxxxxxxxxxxx.supabase.co`) -> bedzie `SUPABASE_URL`
   - **service_role secret** (ten SECRETny, nie anon!) -> bedzie `SUPABASE_SERVICE_ROLE_KEY`

   > UWAGA: `service_role` ma pelny dostep do bazy. Trzymaj go TYLKO w GitHub Secrets, NIGDY w repo ani frontendzie.

---

## Krok 3. Klucz OpenAI (5 min)

1. Wejdz na https://platform.openai.com/signup
2. Po zalozeniu konta dodaj kart i doladuj **5 USD** w **Settings -> Billing -> Add to credit balance**. Tyle wystarczy na kilka miesiecy.
3. Wejdz w **API keys -> Create new secret key**:
   - Name: `nabory-prod`
   - Permissions: **All**
4. Skopiuj klucz (zaczyna sie od `sk-proj-...`) - bedzie `OPENAI_API_KEY`. Mozna go zobaczyc TYLKO RAZ.

---

## Krok 4. Konto Resend (mail) (5 min)

1. Zaloz konto na https://resend.com (darmowy plan: 100 maili/dzien, ~3000/mies - wystarczy z duza rezerwa).
2. **Domain verification** (zalecane, ~5 min):
   - **Domains -> Add Domain**: wpisz `inwestycjepomorze.pl`.
   - Dodaj rekordy DNS (SPF, DKIM, DMARC) wedlug instrukcji Resend - to robi sie raz w panelu Twojego dostawcy DNS (np. OVH, home.pl, Cloudflare).
   - Po weryfikacji bedzie mozna wysylac z `agent@inwestycjepomorze.pl`.

   > Jesli nie chcesz teraz weryfikowac domeny - mozesz tymczasowo uzyc `MAIL_FROM=onboarding@resend.dev`. Maile beda dochodzic, ale czasem do spamu i tylko na adresy na koncie Resend.

3. **API Keys -> Create API Key**:
   - Name: `nabory-prod`
   - Permission: **Sending access**
   - Domain: wybrana
4. Skopiuj klucz (`re_...`) - bedzie `RESEND_API_KEY`.

---

## Krok 5. Google Sheets - panel akceptacji (10 min)

### 5a. Utworzenie Service Account (Google Cloud)

1. Wejdz na https://console.cloud.google.com
2. **New Project** -> nazwa np. `inwestycje-pomorze-agent`
3. **APIs & Services -> Library**: znajdz i wlacz:
   - **Google Sheets API**
   - **Google Drive API**
4. **APIs & Services -> Credentials -> Create Credentials -> Service Account**:
   - Name: `agent-naborow`
   - Skip role assignment (nie dawaj zadnej roli na poziomie projektu)
   - Done
5. Po utworzeniu kliknij na service account -> **Keys -> Add Key -> Create new key -> JSON**.
6. Pobierze sie plik JSON. **NIE commituj go do repo!** Zachowaj w bezpiecznym miejscu (np. password manager).
7. Skopiuj adres email service accountu (z pola `client_email` w JSON, lub z dashboardu, np. `agent-naborow@inwestycje-pomorze-agent.iam.gserviceaccount.com`).

### 5b. Utworzenie arkusza Google

1. Wejdz na https://sheets.google.com -> **Pusty arkusz**
2. Nazwij go: **Nabory - panel Malgorzaty**
3. **Udostepnij** (przycisk Share w prawym gornym):
   - Wklej email service accountu z kroku 5a
   - Uprawnienie: **Editor**
   - Odznacz "Notify people"
4. Udostepnij dodatkowo Malgorzacie (`gosiagrzyska@gmail.com`) z uprawnieniem **Editor**.
5. Skopiuj **ID arkusza** z URL: `https://docs.google.com/spreadsheets/d/THIS_PART/edit` -> bedzie `GOOGLE_SHEET_ID`.

---

## Krok 6. GitHub Actions Secrets (5 min)

W repo na GitHub: **Settings -> Secrets and variables -> Actions -> New repository secret**.

Dodaj nastepujace sekrety (kazdy osobno):

| Secret | Wartosc |
|--------|---------|
| `SUPABASE_URL` | URL z Kroku 2 |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role z Kroku 2 |
| `OPENAI_API_KEY` | klucz z Kroku 3 |
| `RESEND_API_KEY` | klucz z Kroku 4 |
| `MAIL_FROM` | np. `Agent Naborow <agent@inwestycjepomorze.pl>` lub `onboarding@resend.dev` na start |
| `MAIL_TO` | `gosiagrzyska@gmail.com` |
| `GOOGLE_CREDENTIALS_JSON` | **caly** plik JSON z Kroku 5a, wklejony jako jedna wartosc |
| `GOOGLE_SHEET_ID` | ID z Kroku 5b |

---

## Krok 7. Pierwszy dry-run (2 min)

1. W repo na GitHub: **Actions -> Daily naboru run -> Run workflow** (przycisk po prawej, branch `main`).
2. Po ~5-10 min sprawdz:
   - **Actions -> ostatni run** powinien byc zielony
   - **Supabase -> Table Editor -> calls** powinno miec wpisy
   - **Skrzynka gosiagrzyska@gmail.com** powinna miec mail
   - **Arkusz Google** powinien miec wpisy w zakladce "Nowe nieprzejrzane"

Jesli cos nie dziala - przeczytaj logi w Actions, ostatnie kroki maja jasne komunikaty bledow po polsku.

---

## Krok 8. Wlaczenie codziennego harmonogramu

Cron jest juz wpisany w `.github/workflows/daily.yml` (codziennie 6:00 UTC = 7:00/8:00 PL). Wystarczy ze workflow istnieje na branchu `main` - GitHub Actions sam go uruchomi.

> Pierwsze 1-3 dni warto codziennie sprawdzic logi w Actions, zeby wylapac kapryszacych zrodel.

---

## Lokalne uruchomienie (opcjonalne, dla debugowania)

Jesli chcesz uruchomic agenta lokalnie (np. zeby przetestowac nowe zrodlo):

```powershell
cd c:\Users\SPCX\Desktop\nabory
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# Wypelnij .env na podstawie .env.example
cp .env.example .env
# (otworz .env w edytorze i wpisz wartosci)

# Dry-run (nie zapisuje, nie wysyla maila)
$env:DRY_RUN="yes"; python -m nabory.main

# Pelny run (lokalny, zapisuje do Supabase, wysyla mail)
python -m nabory.main
```

---

## Co dalej

- **Etap 1-3** (MVP) - cale zaimplementowane, dziala po wykonaniu Krokow 1-8 powyzej.
- **Etap 4** (integracja z inwestycjepomorze.pl) - patrz `docs/etap-4-integracja.md`.
- **Etap 5** (newsletter klientow) - patrz `docs/etap-5-newsletter.md`.
- **Etap 6** (RAG, Telegram bot) - patrz `docs/etap-6-roadmapa.md`.

Jesli Malgorzata bedzie chciala dodac nowe zrodlo - patrz `README.md`, sekcja "Jak dodac nowa strone".
