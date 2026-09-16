/**
 * Story Scout Next — main SPA controller.
 * Static GitHub Pages app: stories.json (+ optional twitter_stories.json),
 * Dexie cache, Orama search, filters, cards, loadout, detail, custom stories,
 * clip link-outs, night/day + brand toggle, PWA offline.
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
    ].forEach((id) => {
      els[id] = $(id);
    });
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
      const seen = new Set(merged.map((s) => String(s.id)));
      for (const s of extra) {
        if (!seen.has(String(s.id))) {
          merged.push(s);
          seen.add(String(s.id));
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
    await applyFilters();
  }

  function updateStatus() {
    const count = allStories.length;
    if (els["story-count"]) els["story-count"].textContent = String(count);
    const gen =
      (lastPayloadMeta && lastPayloadMeta.generated_at) ||
      null;
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
    const slot = (els["filter-slot"] && els["filter-slot"].value) || "";
    const sort = (els["filter-sort"] && els["filter-sort"].value) || "score";
    const caOnly = els["filter-canadian"] && els["filter-canadian"].checked;
    const clipsOnly = els["filter-clips"] && els["filter-clips"].checked;

    let list = allStories.slice();

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

  function renderCards() {
    const root = els["stories-list"];
    if (!root) return;
    if (!visibleStories.length) {
      root.innerHTML = "";
      if (els["empty-state"]) els["empty-state"].hidden = false;
      return;
    }
    if (els["empty-state"]) els["empty-state"].hidden = true;

    root.innerHTML = visibleStories
      .map((s) => {
        const ca = s.entities && s.entities.is_canadian ? "🇨🇦" : "";
        const clip = SSClips.clipCountBadge(s.clips);
        return `<article class="story-card${s.is_backup ? " is-backup" : ""}" role="listitem" tabindex="0" data-id="${SSClips.escapeAttr(s.id)}">
          <div class="card-top">
            <span class="cat-pill">${SSClips.escapeHtml(s.category || "")}</span>
            <span class="score-pill">${Number(s.score || 0).toFixed(0)}</span>
          </div>
          <h3 class="card-title">${SSClips.escapeHtml(s.title || "")}</h3>
          <p class="card-angle">${SSClips.escapeHtml(s.angle || "")}</p>
          <div class="card-meta">
            <span>${SSClips.escapeHtml(s.slot || "").toUpperCase()}</span>
            <span>${SSClips.escapeHtml(s.date || "")}</span>
            <span>${SSClips.escapeHtml(s.source || "")}</span>
            <span>${ca}</span>
            ${clip}
          </div>
          <div class="card-actions">
            <button type="button" class="nes-btn is-primary" data-act="add" data-id="${SSClips.escapeAttr(s.id)}">+ Loadout</button>
            <button type="button" class="nes-btn" data-act="detail" data-id="${SSClips.escapeAttr(s.id)}">Detail</button>
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
        if (btn.dataset.act === "add") SSLoadout.addStory(id);
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
    els["detail-body"].innerHTML = `
      <div class="detail-cat">${SSClips.escapeHtml(s.category || "")} · score ${SSClips.escapeHtml(String(s.score))} · ${SSClips.escapeHtml((s.slot || "").toUpperCase())}</div>
      <h2 class="detail-title">${SSClips.escapeHtml(s.title || "")}</h2>
      <p>${SSClips.escapeHtml(s.angle || "")}</p>
      <div class="detail-section"><h3>Summary</h3><p>${SSClips.escapeHtml(s.summary || "")}</p></div>
      <div class="detail-section"><h3>Bullets</h3><ul>${bullets || "<li>—</li>"}</ul></div>
      <div class="detail-section"><h3>Debate</h3><p>${SSClips.escapeHtml(s.debate || "")}</p></div>
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
        <button type="button" class="nes-btn is-primary" id="detail-add">+ Loadout</button>
      </div>
    `;
    const addBtn = document.getElementById("detail-add");
    if (addBtn) addBtn.addEventListener("click", () => SSLoadout.addStory(s.id));
    els["detail-dialog"].showModal();
  }

  function brandLabel() {
    const brand = document.documentElement.getAttribute("data-brand") || "daily-goods";
    return brand === "jaystation" ? "Jaystation · Radio Prep" : "Daily Goods · Radio Prep";
  }

  async function applyThemeSettings() {
    const theme = await SSStorage.loadSetting("theme", "night");
    const brand = await SSStorage.loadSetting("brand", "daily-goods");
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.setAttribute("data-brand", brand);
    if (els["btn-theme"]) els["btn-theme"].textContent = theme === "night" ? "NIGHT" : "DAY";
    if (els["btn-brand"]) els["btn-brand"].textContent = brand === "jaystation" ? "JS" : "DG";
    if (els["brand-label"]) els["brand-label"].textContent = brandLabel();
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
      el.addEventListener(evt, () => applyFilters());
    });

    if (els["btn-theme"]) {
      els["btn-theme"].addEventListener("click", async () => {
        const cur = document.documentElement.getAttribute("data-theme") || "night";
        const next = cur === "night" ? "day" : "night";
        await SSStorage.saveSetting("theme", next);
        await applyThemeSettings();
      });
    }

    if (els["btn-brand"]) {
      els["btn-brand"].addEventListener("click", async () => {
        const cur = document.documentElement.getAttribute("data-brand") || "daily-goods";
        const next = cur === "daily-goods" ? "jaystation" : "daily-goods";
        await SSStorage.saveSetting("brand", next);
        await applyThemeSettings();
      });
    }

    if (els["btn-refresh"]) {
      els["btn-refresh"].addEventListener("click", async () => {
        els["btn-refresh"].disabled = true;
        try {
          await bootstrapStories();
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
      els["custom-form"].addEventListener("close", async () => {
        // handled via submit
      });
      els["custom-form"].addEventListener("submit", async (e) => {
        // dialog form method=dialog — read returnValue
      });
      // Use button click interception for Add
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
        await applyFilters();
      });
    }

    if (els["btn-save-loadout"]) {
      els["btn-save-loadout"].addEventListener("click", async () => {
        await SSLoadout.save();
        alert("Loadout saved locally.");
      });
    }
    if (els["btn-load-loadout"]) {
      els["btn-load-loadout"].addEventListener("click", async () => {
        await SSLoadout.load();
      });
    }
    if (els["btn-clear-loadout"]) {
      els["btn-clear-loadout"].addEventListener("click", () => SSLoadout.clear());
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
      .register("./sw.js")
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
    wireUi();
    registerSw();
    try {
      await bootstrapStories();
      await SSLoadout.load();
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
