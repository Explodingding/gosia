/**
 * Integracja formularza newsletter na inwestycjepomorze.pl z Supabase Edge Function.
 *
 * Strona ma juz <form id="newsletterForm">. Ten skrypt podpina submit-handler,
 * ktory wywoluje funkcje subscribe i pokazuje toast-y.
 */

(function () {
  "use strict";

  const FUNCTION_URL = (function () {
    const meta = document.querySelector('meta[name="supabase-url"]');
    if (!meta) return null;
    return `${meta.getAttribute("content").replace(/\/$/, "")}/functions/v1/subscribe`;
  })();

  const form = document.getElementById("newsletterForm");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!FUNCTION_URL) {
      showStatus("Brak konfiguracji - skontaktuj sie z administratorem strony.", "error");
      return;
    }

    const formData = new FormData(form);
    const interests = Array.from(form.querySelectorAll('input[name="interests"]:checked'))
      .map((i) => i.value);
    const consentEl = form.querySelector('input[name="consent"], input[type="checkbox"][required]');
    const consent = consentEl ? consentEl.checked : true;

    const payload = {
      email: (formData.get("email") || "").trim(),
      name: (formData.get("name") || "").trim() || null,
      company: (formData.get("company") || "").trim() || null,
      interests,
      consent,
    };

    if (!payload.email) {
      showStatus("Podaj prawidlowy adres email.", "error");
      return;
    }
    if (interests.length === 0) {
      showStatus("Wybierz przynajmniej jedna kategorie zainteresowan.", "error");
      return;
    }
    if (!consent) {
      showStatus("Wymagana zgoda na przetwarzanie danych.", "error");
      return;
    }

    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.dataset.originalText = submitBtn.textContent;
      submitBtn.textContent = "Wysylam...";
    }

    try {
      const res = await fetch(FUNCTION_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        showStatus(
          data.message || "Sprawdz skrzynke i potwierdz subskrypcje (link w mailu).",
          "success",
        );
        form.reset();
      } else {
        showStatus(
          data.error || "Nie udalo sie zapisac. Sprobuj ponownie za chwile.",
          "error",
        );
      }
    } catch (err) {
      console.error("[newsletter] error", err);
      showStatus("Blad polaczenia. Sprawdz internet i sprobuj ponownie.", "error");
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = submitBtn.dataset.originalText || "Zapisz sie do newslettera";
      }
    }
  });

  function showStatus(text, type) {
    let el = document.getElementById("newsletter-status");
    if (!el) {
      el = document.createElement("div");
      el.id = "newsletter-status";
      el.className = "mt-4 p-3 rounded-md text-sm";
      form.appendChild(el);
    }
    el.textContent = text;
    el.className = "mt-4 p-3 rounded-md text-sm " + (
      type === "success"
        ? "bg-green-100 border border-green-300 text-green-800"
        : "bg-red-100 border border-red-300 text-red-800"
    );
    setTimeout(() => {
      if (el && el.parentNode) el.parentNode.removeChild(el);
    }, 8000);
  }
})();
