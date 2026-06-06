// Minimal client-side glue: show the spinner overlay whenever a form
// marked data-spinner is submitted, so the consultant gets a clear "we are
// talking to Claude" signal during long-running calls.

(function () {
  "use strict";

  const overlay = document.getElementById("spinner-overlay");
  if (!overlay) return;

  function showSpinner(label) {
    if (label) {
      const node = overlay.querySelector(".spinner-label");
      if (node) node.textContent = label;
    }
    overlay.classList.remove("hidden");
    overlay.setAttribute("aria-hidden", "false");
  }

  document.addEventListener("submit", function (event) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (!form.hasAttribute("data-spinner")) return;
    showSpinner(form.getAttribute("data-spinner-label"));
  });

  // Hide the spinner if the user uses the browser's back button after a
  // submission — page is restored from bfcache with the overlay still visible.
  window.addEventListener("pageshow", function () {
    overlay.classList.add("hidden");
    overlay.setAttribute("aria-hidden", "true");
  });
})();

// Chip-input widget. Each .chip-input wraps a hidden <textarea name="..."> that
// carries the actual form value (one chip per line) — the visible field is a
// container of teal-tinted "chips" plus a free-typing input. Adding a chip
// rewrites the textarea, so server-side handling needs no changes.
(function () {
  "use strict";

  function escapeHTML(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function parseInitial(textarea) {
    return (textarea.value || "")
      .split(/\r?\n/)
      .map(function (s) { return s.trim(); })
      .filter(Boolean);
  }

  function syncTextarea(textarea, items) {
    textarea.value = items.join("\n");
  }

  function renderChips(host, items, tone) {
    host.innerHTML = items.map(function (label, i) {
      return (
        '<span class="chip chip-' + tone + '" data-i="' + i + '">' +
          '<span class="chip-label">' + escapeHTML(label) + '</span>' +
          '<button type="button" class="chip-remove" aria-label="Remove">×</button>' +
        '</span>'
      );
    }).join("");
  }

  function init(wrap) {
    var textarea = wrap.querySelector("textarea");
    var input    = wrap.querySelector(".chip-typer");
    var chips    = wrap.querySelector(".chip-list");
    var tone     = wrap.getAttribute("data-tone") || "default";
    if (!textarea || !input || !chips) return;

    var items = parseInitial(textarea);
    renderChips(chips, items, tone);

    function commit() {
      var v = input.value.trim().replace(/,$/, "");
      if (!v) return;
      if (items.indexOf(v) === -1) items.push(v);
      input.value = "";
      renderChips(chips, items, tone);
      syncTextarea(textarea, items);
    }

    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === ",") { e.preventDefault(); commit(); }
      else if (e.key === "Backspace" && !input.value && items.length) {
        items.pop();
        renderChips(chips, items, tone);
        syncTextarea(textarea, items);
      }
    });
    input.addEventListener("blur", commit);

    chips.addEventListener("click", function (e) {
      var btn = e.target.closest && e.target.closest(".chip-remove");
      if (!btn) return;
      var chip = btn.closest(".chip");
      var i = chip && parseInt(chip.getAttribute("data-i"), 10);
      if (isNaN(i)) return;
      items.splice(i, 1);
      renderChips(chips, items, tone);
      syncTextarea(textarea, items);
    });

    // Clicking the wrapper anywhere focuses the typer.
    wrap.addEventListener("click", function (e) {
      if (e.target === wrap || e.target === chips) input.focus();
    });
  }

  document.querySelectorAll("[data-chip-input]").forEach(init);
})();

// Live word counter for InMail draft textareas, plus a copy-to-clipboard
// button. The 150-word cap mirrors the CLI's check_draft().
(function () {
  "use strict";

  function wordsIn(text) {
    return (text.trim().match(/\S+/g) || []).length;
  }

  function update(textarea) {
    const form = textarea.closest("form");
    const counter = form && form.querySelector(".wordcount");
    if (!counter) return;
    const limit = parseInt(counter.getAttribute("data-limit") || "0", 10);
    const n = wordsIn(textarea.value);
    counter.textContent = limit ? `${n} / ${limit} words` : `${n} words`;
    counter.classList.toggle("over-limit", limit > 0 && n > limit);
  }

  document.querySelectorAll("textarea[data-wordcount]").forEach(function (ta) {
    update(ta);
    ta.addEventListener("input", function () {
      update(ta);
    });
  });

  document.addEventListener("click", function (event) {
    const btn = event.target.closest("[data-copy]");
    if (!btn) return;
    // Source: an explicit data-copy-target selector (works anywhere), or the
    // first textarea in the button's form (the InMail draft pattern).
    let text = null;
    const targetSel = btn.getAttribute("data-copy-target");
    if (targetSel) {
      const el = document.querySelector(targetSel);
      if (el) text = el.value !== undefined ? el.value : el.textContent;
    } else {
      const form = btn.closest("form");
      const ta = form && form.querySelector("textarea");
      if (ta) text = ta.value;
    }
    if (text == null || !navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(function () {
      const original = btn.textContent.trim();
      btn.textContent = btn.getAttribute("data-copied-label") || "Copied ✓";
      setTimeout(function () {
        btn.textContent = original;
      }, 1500);
    });
  });
})();
