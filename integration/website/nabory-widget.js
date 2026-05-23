/**
 * Widget naborow dla inwestycjepomorze.pl
 *
 * Pobiera opublikowane nabory z Supabase i renderuje je w istniejacych
 * kontenerach na stronie:
 *   #fundusze-calls-list   - lista naborow
 *   #fundusze-programs-list - lista programow (agregat tagow)
 *   #fundusze-status       - dropdown filtra (Trwa / Nadchodzi / Zakonczone / Wszystkie)
 *   #fundusze-count        - licznik widocznych naborow
 *   #fundusze-updated      - data ostatniej publikacji
 *
 * Wymaga w HTML:
 *   <meta name="supabase-url" content="https://xxxx.supabase.co">
 *   <meta name="supabase-anon-key" content="eyJ...">
 * lub konfiguracji w window.NABORY_CONFIG = {url, anonKey}.
 *
 * Style: Tailwind CSS (uzywany juz na stronie).
 */

(function () {
  "use strict";

  const CONFIG = (function () {
    if (window.NABORY_CONFIG) return window.NABORY_CONFIG;
    const meta = (name) => {
      const el = document.querySelector(`meta[name="${name}"]`);
      return el ? el.getAttribute("content") : null;
    };
    return {
      url: meta("supabase-url"),
      anonKey: meta("supabase-anon-key"),
    };
  })();

  const STATUS_FILTER_OPTIONS = [
    { value: "all",       label: "Wszystkie" },
    { value: "open",      label: "Trwa" },
    { value: "upcoming",  label: "Nadchodzi" },
    { value: "closed",    label: "Zakonczone" },
  ];

  const PROGRAM_LABELS = {
    "feng": "FENG",
    "fe-pomorze": "FE Pomorze",
    "kpo": "KPO",
    "kpo-cyfryzacja": "KPO - cyfryzacja",
    "kpo-zielona": "KPO - zielona",
    "kpo-innowacje": "KPO - innowacje",
    "parp": "PARP",
    "ncbr": "NCBR",
    "rpo": "RPO",
    "bur": "BUR",
  };

  const BENEFICIARY_LABELS = {
    msp: "MSP",
    ngo: "NGO",
    samorzad: "Samorzad",
    startup: "Start-up",
    duza_firma: "Duza firma",
    rolnictwo: "Rolnictwo",
    osoba_fizyczna: "Osoba fizyczna",
    inne: "Inne",
  };

  const state = {
    calls: [],
    filter: { status: "all", program: null, search: "" },
  };

  // ---------------------------------------------------------------- helpers

  function fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric" });
  }

  function fmtAmount(min, max) {
    const fmt = (v) => Number(v).toLocaleString("pl-PL", { maximumFractionDigits: 0 }) + " PLN";
    if (min && max && min !== max) return `${fmt(min)} - ${fmt(max)}`;
    if (max) return `do ${fmt(max)}`;
    if (min) return `od ${fmt(min)}`;
    return null;
  }

  function deadlineStatus(call) {
    if (!call.deadline) return "upcoming";
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const d = new Date(call.deadline);
    if (isNaN(d)) return "upcoming";
    if (d < today) return "closed";
    return "open";
  }

  function badge(text, color) {
    return `<span class="inline-block px-2 py-0.5 text-xs font-semibold rounded-full bg-${color}-100 text-${color}-800">${escapeHtml(text)}</span>`;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  // ---------------------------------------------------------------- fetching

  async function fetchPublishedCalls() {
    if (!CONFIG.url || !CONFIG.anonKey) {
      console.error("[nabory] Brak konfiguracji Supabase (supabase-url / supabase-anon-key).");
      return [];
    }
    const url = `${CONFIG.url.replace(/\/$/, "")}/rest/v1/published_calls_v?order=deadline.asc.nullslast,published_at.desc&limit=200`;
    const res = await fetch(url, {
      headers: {
        apikey: CONFIG.anonKey,
        Authorization: `Bearer ${CONFIG.anonKey}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      console.error("[nabory] Blad pobrania naborow:", res.status, await res.text());
      return [];
    }
    return await res.json();
  }

  // ---------------------------------------------------------------- rendering

  function renderStatus() {
    const el = document.getElementById("fundusze-status");
    if (!el) return;
    if (el.tagName === "SELECT") {
      el.innerHTML = STATUS_FILTER_OPTIONS
        .map((o) => `<option value="${o.value}">${o.label}</option>`)
        .join("");
      el.value = state.filter.status;
      el.addEventListener("change", () => {
        state.filter.status = el.value;
        renderCalls();
        renderCount();
      });
    } else {
      el.innerHTML = STATUS_FILTER_OPTIONS
        .map(
          (o) =>
            `<button data-status="${o.value}" class="px-3 py-1 text-sm rounded-md border ${
              o.value === state.filter.status
                ? "bg-primary-600 text-white border-primary-600"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
            }">${o.label}</button>`
        )
        .join(" ");
      el.querySelectorAll("button").forEach((btn) => {
        btn.addEventListener("click", () => {
          state.filter.status = btn.getAttribute("data-status");
          renderStatus();
          renderCalls();
          renderCount();
        });
      });
    }
  }

  function renderPrograms() {
    const el = document.getElementById("fundusze-programs-list");
    if (!el) return;
    const counts = {};
    state.calls.forEach((c) => {
      (c.tags || []).forEach((t) => {
        if (PROGRAM_LABELS[t]) counts[t] = (counts[t] || 0) + 1;
      });
    });
    const items = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    el.innerHTML = `
      <button data-program="" class="px-3 py-1 text-sm rounded-md border ${state.filter.program ? "bg-white text-gray-700 border-gray-300" : "bg-primary-600 text-white border-primary-600"}">Wszystkie programy</button>
      ${items
        .map(
          ([slug, count]) =>
            `<button data-program="${slug}" class="px-3 py-1 text-sm rounded-md border ${
              state.filter.program === slug
                ? "bg-primary-600 text-white border-primary-600"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
            }">${PROGRAM_LABELS[slug] || slug} <span class="text-xs opacity-75">(${count})</span></button>`
        )
        .join(" ")}
    `;
    el.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.filter.program = btn.getAttribute("data-program") || null;
        renderPrograms();
        renderCalls();
        renderCount();
      });
    });
  }

  function filterCalls() {
    return state.calls.filter((c) => {
      if (state.filter.status !== "all") {
        if (deadlineStatus(c) !== state.filter.status) return false;
      }
      if (state.filter.program) {
        if (!(c.tags || []).includes(state.filter.program)) return false;
      }
      return true;
    });
  }

  function renderCalls() {
    const el = document.getElementById("fundusze-calls-list");
    if (!el) return;
    const list = filterCalls();
    if (list.length === 0) {
      el.innerHTML = `
        <div class="text-center py-12 text-gray-500">
          <i class="fas fa-search text-4xl mb-3 opacity-50"></i>
          <p>Brak naborow pasujacych do filtrow.</p>
          <p class="text-sm mt-2">Sprobuj zmienic filtr statusu lub programu, albo wroc pozniej - lista jest aktualizowana codziennie.</p>
        </div>`;
      return;
    }
    el.innerHTML = list.map(renderCallCard).join("");
  }

  function renderCallCard(c) {
    const status = deadlineStatus(c);
    const statusBadge =
      status === "open"
        ? badge("Trwa", "green")
        : status === "upcoming"
        ? badge("Nadchodzi", "blue")
        : badge("Zakonczony", "gray");
    const benef = c.beneficiary ? badge(BENEFICIARY_LABELS[c.beneficiary] || c.beneficiary, "indigo") : "";
    const region = c.region
      ? `<span class="inline-flex items-center text-xs text-gray-600"><i class="fas fa-map-marker-alt mr-1"></i>${escapeHtml(c.region)}</span>`
      : "";
    const program = c.program
      ? `<span class="text-xs font-semibold text-primary-700">${escapeHtml(c.program)}</span>`
      : "";
    const amount = fmtAmount(c.amount_min, c.amount_max);
    const amountHtml = amount
      ? `<span class="inline-flex items-center text-xs text-gray-700"><i class="fas fa-coins mr-1"></i>${escapeHtml(amount)}</span>`
      : "";
    const deadlineHtml = c.deadline
      ? `<span class="inline-flex items-center text-xs text-gray-700"><i class="fas fa-calendar-alt mr-1"></i>termin: <strong class="ml-1">${fmtDate(c.deadline)}</strong></span>`
      : c.deadline_text
      ? `<span class="inline-flex items-center text-xs text-gray-700"><i class="fas fa-calendar-alt mr-1"></i>${escapeHtml(c.deadline_text)}</span>`
      : "";
    return `
      <article class="bg-white border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow">
        <div class="flex items-start justify-between gap-3 mb-2">
          <div class="flex flex-wrap items-center gap-2">
            ${statusBadge}${benef}${program}
          </div>
          <a href="${escapeHtml(c.url)}" target="_blank" rel="noopener"
             class="text-xs text-primary-600 hover:text-primary-800 whitespace-nowrap">
            Oryginal <i class="fas fa-external-link-alt ml-1"></i>
          </a>
        </div>
        <h3 class="text-base md:text-lg font-semibold text-gray-900 mb-2">
          <a href="${escapeHtml(c.url)}" target="_blank" rel="noopener" class="hover:text-primary-700">
            ${escapeHtml(c.title)}
          </a>
        </h3>
        ${c.summary ? `<p class="text-sm text-gray-700 mb-3">${escapeHtml(c.summary)}</p>` : ""}
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
          ${region}${amountHtml}${deadlineHtml}
        </div>
      </article>
    `;
  }

  function renderCount() {
    const el = document.getElementById("fundusze-count");
    if (!el) return;
    const visible = filterCalls().length;
    const total = state.calls.length;
    el.textContent = visible === total ? `${total}` : `${visible}/${total}`;
  }

  function renderUpdated() {
    const el = document.getElementById("fundusze-updated");
    if (!el || !state.calls.length) return;
    const latest = state.calls
      .map((c) => c.published_at)
      .filter(Boolean)
      .sort()
      .reverse()[0];
    if (latest) el.textContent = fmtDate(latest);
  }

  // ---------------------------------------------------------------- init

  async function init() {
    state.calls = await fetchPublishedCalls();
    renderStatus();
    renderPrograms();
    renderCalls();
    renderCount();
    renderUpdated();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
