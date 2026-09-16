/**
 * Story Scout Next — main SPA controller.
 * Static GitHub Pages app: stories.json (+ optional twitter_stories.json),
 * Dexie cache, Orama search, filters, cards, loadout, detail, custom stories,
 * clip link-outs, night/day + brand toggle, Arcade intro, PWA offline.
 */
(function () {
  "use strict";

  const CATEGORIES = [
    "THE LIST",
    "ENTERTAINMENT",
    "BREAKOUT WATCH",
    "LIFESTYLE CHAT",
    "CANADIAN NEWS",
    "TECH",
    "SPORTS",
    "CLOSER",
  ];

  let allStories = [];
  let visibleStories = [];
  let lastPayloadMeta = null;
  /** @type {{ date: string, slot: string } | null} */
  let activeEdition = null;
  /** @type {Array<{ date: string, weekday: string, dateLabel: string, am: number, pm: number, total: number }>} */
  let rundownIndex = [];

  const els = {};

  function $(id) {
    return document.getElementById(id);
  }

  function cacheEls() {
    [
      "stories-list",
      "empty-state",
      "search-input",
      "filter-category",
      "filter-slot",
      "filter-sort",
      "filter-canadian",
      "filter-clips",
      "btn-theme",
      "btn-brand",
      "btn-refresh",
      "btn-custom",
      "btn-save-loadout",
      "btn-load-loadout",
      "btn-prep-sheet",
      "btn-clear-loadout",
      "btn-print-prep",
      "btn-back-rundowns",
      "last-updated",
      "story-count",
      "offline-badge",
      "brand-label",
      "detail-dialog",
      "detail-body",
      "custom-dialog",
      "custom-form",
      "prep-dialog",
      "prep-body",
      "pwa-status",
      "intro-screen",
      "app-shell",
      "rundown-view",
      "rundown-grid",
      "rundown-empty",
      "edition-view",
      "edition-label",
      "intro-start",
      "intro-options",
      "intro-options-panel",
      "intro-options-close",
      "intro-theme",
      "intro-theme-opt",
      "intro-brand",
      "intro-title",
      "intro-presents",
      "intro-brand-logo",
      "header-mascot",
      "header-brand-logo",
      "intro-mascot",
      "intro-brand-opt",
      "toast",
    ].forEach((id) => {
      els[id] = $(id);
    });
  }

  function showToast(msg) {
    const t = els["toast"];
    if (!t) return;
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(() => {
      t.hidden = true;
    }, 2200);
  }

  async function fetchJson(path) {
    const res = await fetch(path, { cache: "no-cache" });
    if (!res.ok) throw new Error(path + " " + res.status);
    return res.json();
  }

  function normalizePayload(data) {
    if (Array.isArray(data)) return { stories: data, meta: {} };
    if (data && Array.isArray(data.stories)) {
      return {
        stories: data.stories,
        meta: {
          generated_at: data.generated_at,
          date: data.date,
          slot: data.slot,
          pipeline_version: data.pipeline_version,
          count: data.count,
        },
      };
    }
    return { stories: [], meta: {} };
  }

  async function loadRemoteStories() {
    const primary = await fetchJson("data/stories.json");
    const { stories, meta } = normalizePayload(primary);
    let merged = stories.slice();

    try {
      const tw = await fetchJson("data/twitter_stories.json");
      const extra = normalizePayload(tw).stories;
      const byId = new Map(merged.map((s) => [String(s.id), s]));
      for (const s of extra) {
        const id = String(s.id);
        const existing = byId.get(id);
        if (existing) {
          // Clip-attach on load: append unique clips by url (no duplicate story)
          if (s.clips && s.clips.length) {
            existing.clips = existing.clips || [];
            const seenUrl = new Set(
              existing.clips.map((c) => String((c && c.url) || "").toLowerCase())
            );
            for (const c of s.clips) {
              const u = String((c && c.url) || "").toLowerCase();
              if (u && !seenUrl.has(u)) {
                existing.clips.push(c);
                seenUrl.add(u);
              }
            }
          }
        } else {
          merged.push(s);
          byId.set(id, s);
        }
      }
    } catch (_) {
      /* optional file */
    }

    lastPayloadMeta = meta;
    return merged;
  }

  async function bootstrapStories() {
    try {
      const remote = await loadRemoteStories();
      allStories = remote;
      await SSStorage.saveStories(allStories, {
        syncedAt: new Date().toISOString(),
        generated_at: lastPayloadMeta && lastPayloadMeta.generated_at,
        count: allStories.length,
      });
    } catch (err) {
      console.warn("[app] remote load failed, using Dexie cache", err);
      allStories = await SSStorage.loadStories();
      if (!allStories.length) {
        throw err;
      }
    }
    SSLoadout.setStoryIndex(allStories);
    if (SSSearch.whenReady) await SSSearch.whenReady(3000);
    await SSSearch.rebuild(allStories);
    updateStatus();
    buildRundownIndex();
    if (activeEdition) {
      await applyFilters();
    } else {
      renderRundownPicker();
      showRundownView();
    }
  }

  function updateStatus() {
    const count = allStories.length;
    if (els["story-count"]) els["story-count"].textContent = String(count);
    const gen = (lastPayloadMeta && lastPayloadMeta.generated_at) || null;
    const label = gen
      ? new Date(gen).toLocaleString("en-CA", { timeZone: "America/Toronto" }) + " ET"
      : "cached / unknown";
    if (els["last-updated"]) els["last-updated"].textContent = "Last updated: " + label;
    if (els["offline-badge"]) {
      els["offline-badge"].hidden = navigator.onLine;
    }
  }

  async function applyFilters() {
    const q = (els["search-input"] && els["search-input"].value) || "";
    const cat = (els["filter-category"] && els["filter-category"].value) || "";
    const slot =
      (activeEdition && activeEdition.slot) ||
      ((els["filter-slot"] && els["filter-slot"].value) || "");
    const sort = (els["filter-sort"] && els["filter-sort"].value) || "score";
    const caOnly = els["filter-canadian"] && els["filter-canadian"].checked;
    const clipsOnly = els["filter-clips"] && els["filter-clips"].checked;

    let list = allStories.slice();

    if (activeEdition && activeEdition.date) {
      list = list.filter((s) => s.date === activeEdition.date);
    }

    if (q.trim()) {
      const ids = await SSSearch.query(q, 200);
      if (ids) {
        const set = new Set(ids.map(String));
        list = list.filter((s) => set.has(String(s.id)));
      } else {
        list = SSSearch.fallbackFilter(list, q);
      }
    }

    if (cat) list = list.filter((s) => s.category === cat);
    if (slot) list = list.filter((s) => s.slot === slot);
    if (caOnly) list = list.filter((s) => s.entities && s.entities.is_canadian);
    if (clipsOnly) list = list.filter((s) => s.clips && s.clips.length);

    list.sort((a, b) => {
      if (sort === "title") return String(a.title || "").localeCompare(String(b.title || ""));
      if (sort === "category") return String(a.category || "").localeCompare(String(b.category || ""));
      if (sort === "date") return String(b.date || "").localeCompare(String(a.date || ""));
      return (Number(b.score) || 0) - (Number(a.score) || 0);
    });

    visibleStories = list;
    renderCards();
  }


  const WEEKDAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
  const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

  function formatRundownDate(iso) {
    const parts = String(iso || "").split("-").map(Number);
    if (parts.length !== 3 || parts.some((n) => !n)) {
      return { weekday: "—", dateLabel: String(iso || "—") };
    }
    const [y, m, d] = parts;
    const dt = new Date(Date.UTC(y, m - 1, d, 12, 0, 0));
    return {
      weekday: WEEKDAYS[dt.getUTCDay()],
      dateLabel: MONTHS[m - 1] + " " + String(d).padStart(2, "0"),
    };
  }

  function buildRundownIndex() {
    const byDate = new Map();
    for (const s of allStories) {
      const date = s.date || "unknown";
      if (!byDate.has(date)) {
        byDate.set(date, { date, am: 0, pm: 0, total: 0 });
      }
      const row = byDate.get(date);
      row.total += 1;
      if (s.slot === "pm") row.pm += 1;
      else row.am += 1;
    }
    rundownIndex = Array.from(byDate.values())
      .sort((a, b) => String(b.date).localeCompare(String(a.date)))
      .map((row) => {
        const fmt = formatRundownDate(row.date);
        return Object.assign({}, row, {
          weekday: fmt.weekday,
          dateLabel: fmt.dateLabel,
        });
      });
  }

  function showRundownView() {
    if (els["rundown-view"]) els["rundown-view"].hidden = false;
    if (els["edition-view"]) els["edition-view"].hidden = true;
  }

  function showEditionView() {
    if (els["rundown-view"]) els["rundown-view"].hidden = true;
    if (els["edition-view"]) els["edition-view"].hidden = false;
  }

  function renderRundownPicker() {
    const root = els["rundown-grid"];
    if (!root) return;
    buildRundownIndex();
    if (!rundownIndex.length) {
      root.innerHTML = "";
      if (els["rundown-empty"]) els["rundown-empty"].hidden = false;
      return;
    }
    if (els["rundown-empty"]) els["rundown-empty"].hidden = true;

    root.innerHTML = rundownIndex
      .map((row) => {
        const amBtn = row.am
          ? `<button type="button" class="edition-btn morning" data-date="${SSClips.escapeAttr(row.date)}" data-slot="am">MORNING</button>`
          : "";
        const pmBtn = row.pm
          ? `<button type="button" class="edition-btn evening" data-date="${SSClips.escapeAttr(row.date)}" data-slot="pm">EVENING</button>`
          : "";
        return `<article class="rundown-card" role="listitem" data-date="${SSClips.escapeAttr(row.date)}">
          <div class="rundown-card-top">
            <img class="rundown-logo pixelated" src="assets/daily-goods-logo.jpeg" alt="Daily Goods" />
            <div class="rundown-date-block">
              <p class="rundown-weekday">${SSClips.escapeHtml(row.weekday)}</p>
              <h3 class="rundown-date">${SSClips.escapeHtml(row.dateLabel)}</h3>
            </div>
          </div>
          <div class="rundown-editions">${amBtn}${pmBtn}</div>
          <p class="rundown-count">${row.total} stor${row.total === 1 ? "y" : "ies"}</p>
        </article>`;
      })
      .join("");

    root.querySelectorAll(".edition-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        openEdition(btn.dataset.date, btn.dataset.slot);
      });
    });
  }

  function openEdition(date, slot) {
    if (!date || !slot) return;
    activeEdition = { date: String(date), slot: String(slot) };
    if (els["filter-slot"]) els["filter-slot"].value = activeEdition.slot;
    const fmt = formatRundownDate(activeEdition.date);
    const slotLabel = activeEdition.slot === "pm" ? "EVENING" : "MORNING";
    if (els["edition-label"]) {
      els["edition-label"].textContent =
        fmt.weekday + " " + fmt.dateLabel + " · " + slotLabel;
    }
    showEditionView();
    applyFilters();
  }

  function backToRundowns() {
    activeEdition = null;
    if (els["filter-slot"]) els["filter-slot"].value = "";
    if (els["search-input"]) els["search-input"].value = "";
    if (els["filter-category"]) els["filter-category"].value = "";
    if (els["filter-canadian"]) els["filter-canadian"].checked = false;
    if (els["filter-clips"]) els["filter-clips"].checked = false;
    if (els["stories-list"]) els["stories-list"].innerHTML = "";
    renderRundownPicker();
    showRundownView();
  }

  function renderCards() {
    const root = els["stories-list"];
    if (!root) return;
    if (!visibleStories.length) {
      root.innerHTML = "";
      if (els["empty-state"]) els["empty-state"].hidden = false;
      return;
    }
    if (els["empty-state"]) els["empty-state"].hidden = true;

    const inLoadout = new Set(SSLoadout.getItems().map((it) => String(it.id)));

    root.innerHTML = visibleStories
      .map((s) => {
        const ca =
          s.entities && s.entities.is_canadian
            ? '<span class="tag tag-ca" title="Canadian">🇨🇦 CA</span>'
            : "";
        const clip = SSClips.clipCountBadge(s.clips);
        const selected = inLoadout.has(String(s.id)) ? " selected" : "";
        const debate = s.debate
          ? `<p class="card-debate">${SSClips.escapeHtml(s.debate)}</p>`
          : "";
        return `<article class="card story-card${s.is_backup ? " is-backup" : ""}${selected}" role="listitem" tabindex="0" data-id="${SSClips.escapeAttr(s.id)}">
          <div class="card-top">
            <span class="tag cat">${SSClips.escapeHtml(s.category || "")}</span>
            <span class="score-pill">${Number(s.score || 0).toFixed(0)}</span>
          </div>
          <h3 class="card-title">${SSClips.escapeHtml(s.title || "")}</h3>
          <p class="card-angle">${SSClips.escapeHtml(s.angle || "")}</p>
          ${debate}
          <div class="card-meta">
            <span>${SSClips.escapeHtml(s.slot || "").toUpperCase()}</span>
            <span>${SSClips.escapeHtml(s.date || "")}</span>
            <span>${SSClips.escapeHtml(s.source || "")}</span>
            ${ca}
            ${clip}
          </div>
          <div class="card-actions">
            <button type="button" class="btn btn-primary" data-act="add" data-id="${SSClips.escapeAttr(s.id)}">+ Loadout</button>
            <button type="button" class="btn" data-act="detail" data-id="${SSClips.escapeAttr(s.id)}">Detail</button>
          </div>
        </article>`;
      })
      .join("");

    root.querySelectorAll(".story-card").forEach((card) => {
      card.addEventListener("click", (e) => {
        if (e.target.closest("button")) return;
        openDetail(card.dataset.id);
      });
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter") openDetail(card.dataset.id);
      });
    });
    root.querySelectorAll("button[data-act]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        if (btn.dataset.act === "add") {
          SSLoadout.addStory(id);
          renderCards();
          showToast("Added to loadout");
        }
        if (btn.dataset.act === "detail") openDetail(id);
      });
    });
  }

  function findStory(id) {
    return allStories.find((s) => String(s.id) === String(id));
  }

  function openDetail(id) {
    const s = findStory(id);
    if (!s || !els["detail-body"] || !els["detail-dialog"]) return;
    const ents = s.entities || {};
    const sent = s.sentiment || {};
    const bullets = (s.bullets || []).map((b) => `<li>${SSClips.escapeHtml(b)}</li>`).join("");
    const caTag = ents.is_canadian ? '<span class="tag tag-ca">🇨🇦 Canadian</span>' : "";
    els["detail-body"].innerHTML = `
      <div class="detail-cat">
        <span class="tag cat">${SSClips.escapeHtml(s.category || "")}</span>
        <span class="detail-score"> score ${SSClips.escapeHtml(String(s.score))}</span>
        · ${SSClips.escapeHtml((s.slot || "").toUpperCase())}
        ${caTag}
      </div>
      <h2 class="detail-title">${SSClips.escapeHtml(s.title || "")}</h2>
      <p>${SSClips.escapeHtml(s.angle || "")}</p>
      <div class="detail-section"><h3>Summary</h3><p>${SSClips.escapeHtml(s.summary || "")}</p></div>
      <div class="detail-section"><h3>Bullets</h3><ul>${bullets || "<li>—</li>"}</ul></div>
      <div class="detail-section"><h3>Debate</h3><p class="detail-debate">${SSClips.escapeHtml(s.debate || "")}</p></div>
      <div class="detail-section"><h3>Entities</h3>
        <p>People: ${SSClips.escapeHtml((ents.people || []).join(", ") || "—")}</p>
        <p>Orgs: ${SSClips.escapeHtml((ents.organizations || []).join(", ") || "—")}</p>
        <p>Places: ${SSClips.escapeHtml((ents.locations || []).join(", ") || "—")}</p>
        <p>Canadian: ${ents.is_canadian ? "yes" : "no"} · Sentiment: ${SSClips.escapeHtml(sent.label || "—")} (${SSClips.escapeHtml(String(sent.compound ?? "—"))})</p>
      </div>
      <div class="detail-section"><h3>Clips (link-out)</h3>${SSClips.renderClipList(s.clips)}</div>
      <div class="detail-section"><h3>Source</h3>
        <p>${SSClips.escapeHtml(s.source || "")} · ${SSClips.escapeHtml(s.source_type || "")}</p>
        ${s.url ? `<p><a href="${SSClips.escapeAttr(s.url)}" target="_blank" rel="noopener noreferrer">Open article ↗</a></p>` : ""}
      </div>
      <div class="card-actions">
        <button type="button" class="btn btn-primary" id="detail-add">+ Loadout</button>
      </div>
    `;
    const addBtn = document.getElementById("detail-add");
    if (addBtn) {
      addBtn.addEventListener("click", () => {
        SSLoadout.addStory(s.id);
        renderCards();
        showToast("Added to loadout");
      });
    }
    els["detail-dialog"].showModal();
  }

  function brandLabel() {
    const brand = document.documentElement.getAttribute("data-brand") || "daily-goods";
    return brand === "jaystation" ? "Jaystation · Radio Prep" : "Daily Goods · Radio Prep";
  }

  function brandShort() {
    const brand = document.documentElement.getAttribute("data-brand") || "daily-goods";
    return brand === "jaystation" ? "JS" : "DG";
  }

  function brandLong() {
    const brand = document.documentElement.getAttribute("data-brand") || "daily-goods";
    return brand === "jaystation" ? "JAYSTATION" : "DAILY GOODS";
  }

  function syncThemeButtons() {
    const theme = document.documentElement.getAttribute("data-theme") || "night";
    const brand = document.documentElement.getAttribute("data-brand") || "jaystation";
    if (els["btn-theme"]) els["btn-theme"].textContent = theme === "night" ? "NIGHT" : "DAY";
    if (els["btn-brand"]) els["btn-brand"].textContent = brandShort();
    if (els["brand-label"]) els["brand-label"].textContent = brandLabel();
    if (els["intro-theme"]) {
      els["intro-theme"].textContent = theme === "night" ? "NIGHT MODE" : "DAY MODE";
    }
    if (els["intro-theme-opt"]) {
      els["intro-theme-opt"].textContent = "THEME: " + (theme === "night" ? "NIGHT" : "DAY");
    }
    if (els["intro-brand"]) {
      els["intro-brand"].textContent =
        brand === "jaystation" ? "♦ SWITCH TO DAILY GOODS" : "♦ SWITCH TO JAYSTATION";
    }
    if (els["intro-brand-opt"]) els["intro-brand-opt"].textContent = "BRAND: " + brandShort();
    if (els["intro-title"]) {
      els["intro-title"].textContent = brand === "jaystation" ? "JAYSTATION" : "THE DAILY GOODS";
    }
    if (els["intro-presents"]) {
      els["intro-presents"].textContent =
        brand === "jaystation" ? "THE DAILY GOODS PRESENTS" : "NOW PLAYING";
    }
    const logo = els["intro-brand-logo"];
    if (logo) logo.hidden = brand !== "daily-goods";
    const headerLogo = els["header-brand-logo"];
    if (headerLogo) headerLogo.hidden = brand !== "daily-goods";
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "day" ? "#e8e4f0" : "#06050f");
  }

  async function applyThemeSettings() {
    const theme = await SSStorage.loadSetting("theme", "night");
    const brand = await SSStorage.loadSetting("brand", "jaystation");
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.setAttribute("data-brand", brand);
    syncThemeButtons();
  }

  async function toggleTheme() {
    const cur = document.documentElement.getAttribute("data-theme") || "night";
    const next = cur === "night" ? "day" : "night";
    await SSStorage.saveSetting("theme", next);
    await applyThemeSettings();
  }

  async function toggleBrand() {
    const cur = document.documentElement.getAttribute("data-brand") || "daily-goods";
    const next = cur === "daily-goods" ? "jaystation" : "daily-goods";
    await SSStorage.saveSetting("brand", next);
    await applyThemeSettings();
  }

  function startApp() {
    if (els["intro-screen"]) {
      els["intro-screen"].classList.add("is-hidden");
      els["intro-screen"].hidden = true;
    }
    if (els["app-shell"]) els["app-shell"].hidden = false;
    if (!activeEdition) {
      renderRundownPicker();
      showRundownView();
    } else {
      showEditionView();
    }
  }

  function wireIntro() {
    if (els["intro-start"]) {
      els["intro-start"].addEventListener("click", startApp);
    }
    if (els["intro-options"]) {
      els["intro-options"].addEventListener("click", () => {
        if (els["intro-options-panel"]) {
          els["intro-options-panel"].hidden = !els["intro-options-panel"].hidden;
        }
      });
    }
    if (els["intro-options-close"]) {
      els["intro-options-close"].addEventListener("click", () => {
        if (els["intro-options-panel"]) els["intro-options-panel"].hidden = true;
      });
    }
    if (els["intro-theme"]) {
      els["intro-theme"].addEventListener("click", () => toggleTheme());
    }
    if (els["intro-theme-opt"]) {
      els["intro-theme-opt"].addEventListener("click", () => toggleTheme());
    }
    if (els["intro-brand"]) {
      els["intro-brand"].addEventListener("click", () => toggleBrand());
    }
    if (els["intro-brand-opt"]) {
      els["intro-brand-opt"].addEventListener("click", () => toggleBrand());
    }
  }

  function wireUi() {
    const filterIds = [
      "search-input",
      "filter-category",
      "filter-slot",
      "filter-sort",
      "filter-canadian",
      "filter-clips",
    ];
    filterIds.forEach((id) => {
      const el = els[id];
      if (!el) return;
      const evt = el.tagName === "INPUT" && el.type === "search" ? "input" : "change";
      el.addEventListener(evt, () => {
        if (id === "filter-slot" && activeEdition && el.value) {
          activeEdition = { date: activeEdition.date, slot: el.value };
          const fmt = formatRundownDate(activeEdition.date);
          const slotLabel = activeEdition.slot === "pm" ? "EVENING" : "MORNING";
          if (els["edition-label"]) {
            els["edition-label"].textContent =
              fmt.weekday + " " + fmt.dateLabel + " · " + slotLabel;
          }
        }
        applyFilters();
      });
    });

    if (els["btn-back-rundowns"]) {
      els["btn-back-rundowns"].addEventListener("click", () => backToRundowns());
    }

    if (els["btn-theme"]) {
      els["btn-theme"].addEventListener("click", () => toggleTheme());
    }

    if (els["btn-brand"]) {
      els["btn-brand"].addEventListener("click", () => toggleBrand());
    }

    if (els["btn-refresh"]) {
      els["btn-refresh"].addEventListener("click", async () => {
        els["btn-refresh"].disabled = true;
        try {
          await bootstrapStories();
          showToast("Stories synced");
        } finally {
          els["btn-refresh"].disabled = false;
        }
      });
    }

    if (els["btn-custom"]) {
      els["btn-custom"].addEventListener("click", () => {
        if (els["custom-form"]) els["custom-form"].reset();
        els["custom-dialog"].showModal();
      });
    }

    if (els["custom-form"]) {
      els["custom-dialog"].addEventListener("close", async () => {
        if (els["custom-dialog"].returnValue !== "ok") return;
        const fd = new FormData(els["custom-form"]);
        const title = String(fd.get("title") || "").trim();
        if (!title) return;
        const bullets = String(fd.get("bullets") || "")
          .split("\n")
          .map((x) => x.trim())
          .filter(Boolean);
        const id = "custom-" + Date.now().toString(36);
        const story = {
          id,
          date: new Date().toLocaleDateString("en-CA", { timeZone: "America/Toronto" }),
          slot: new Date().getHours() < 15 ? "am" : "pm",
          category: String(fd.get("category") || "THE LIST"),
          title,
          angle: String(fd.get("angle") || title),
          bullets,
          debate: String(fd.get("debate") || "Agree or disagree — make your case in 30 seconds."),
          source: "Custom",
          source_type: "custom",
          url: String(fd.get("url") || ""),
          score: 60,
          is_backup: false,
          entities: { people: [], organizations: [], locations: [], is_canadian: true },
          sentiment: { compound: 0, label: "neutral" },
          summary: bullets.join(" ") || title,
          cluster_id: id,
          related_count: 0,
          clips: [],
          meta: {
            ingested_at: new Date().toISOString(),
            source_published_at: new Date().toISOString(),
            pipeline_version: "custom",
          },
        };
        allStories.unshift(story);
        await SSStorage.upsertCustomStory(story);
        SSLoadout.setStoryIndex(allStories);
        await SSSearch.rebuild(allStories);
        updateStatus();
        buildRundownIndex();
        if (activeEdition) {
          await applyFilters();
        } else {
          renderRundownPicker();
        }
        showToast("Custom story added");
      });
    }

    if (els["btn-save-loadout"]) {
      els["btn-save-loadout"].addEventListener("click", async () => {
        await SSLoadout.save();
        showToast("Loadout saved");
      });
    }
    if (els["btn-load-loadout"]) {
      els["btn-load-loadout"].addEventListener("click", async () => {
        await SSLoadout.load();
        renderCards();
        showToast("Loadout loaded");
      });
    }
    if (els["btn-clear-loadout"]) {
      els["btn-clear-loadout"].addEventListener("click", () => {
        SSLoadout.clear();
        renderCards();
        showToast("Loadout cleared");
      });
    }
    if (els["btn-prep-sheet"]) {
      els["btn-prep-sheet"].addEventListener("click", () => {
        els["prep-body"].innerHTML = SSLoadout.buildPrepHtml(brandLabel());
        els["prep-dialog"].showModal();
      });
    }
    if (els["btn-print-prep"]) {
      els["btn-print-prep"].addEventListener("click", () => window.print());
    }

    window.addEventListener("online", updateStatus);
    window.addEventListener("offline", updateStatus);
  }

  function registerSw() {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker
      .register("./sw.js?v=4")
      .then((reg) => {
        if (els["pwa-status"]) els["pwa-status"].textContent = "PWA ready";
        console.info("[sw] registered", reg.scope);
      })
      .catch((err) => {
        if (els["pwa-status"]) els["pwa-status"].textContent = "PWA off";
        console.warn("[sw]", err);
      });
  }

  async function init() {
    cacheEls();
    await applyThemeSettings();
    wireIntro();
    wireUi();
    registerSw();
    try {
      await bootstrapStories();
      await SSLoadout.load();
      if (activeEdition) renderCards();
      else renderRundownPicker();
    } catch (err) {
      if (els["stories-list"]) {
        els["stories-list"].innerHTML =
          '<p class="empty-state">Failed to load stories.json. Check data/ or go online once.</p>';
      }
      console.error(err);
    }
    SSLoadout.render();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
