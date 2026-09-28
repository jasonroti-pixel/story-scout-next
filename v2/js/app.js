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
  let junkIdSet = new Set();

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
      "btn-refresh",
      "btn-junk-folder",
      "btn-custom",
      "btn-custom-picker",
      "btn-select-all",
      "btn-selall-loadout",
      "btn-copy-loadout",
      "btn-print-loadout",
      "btn-email-loadout",
      "btn-clear-loadout",
      "btn-loadout",
      "btn-close-loadout",
      "loadout-pane",
      "prepActions",
      "prepList",
      "prepCount",
      "btn-back-rundowns",
      "last-updated",
      "story-count",
      "offline-badge",
      "brand-label",
      "detail-dialog",
      "detail-body",
      "custom-dialog",
      "custom-form",
      "junk-dialog",
      "junk-list",
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
      "intro-title",
      "intro-presents",
      "intro-brand-logo",
      "header-mascot",
      "header-brand-logo",
      "intro-mascot",
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
    const primary = await fetchJson("../data/stories.json");
    const { stories, meta } = normalizePayload(primary);
    let merged = stories.slice();

    try {
      const tw = await fetchJson("../data/twitter_stories.json");
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
    // Merge user-created custom stories (they persist in this browser's
    // Dexie table; a remote sync never includes them).
    try {
      const customs = await SSStorage.listCustomStories();
      if (customs && customs.length) {
        const seen = new Set(allStories.map((s) => String(s.id)));
        customs.forEach((c) => {
          if (!seen.has(String(c.id))) {
            allStories.unshift(c);
            seen.add(String(c.id));
          }
        });
      }
    } catch (mergeErr) {
      console.warn("[app] custom story merge failed", mergeErr);
    }
    SSLoadout.setStories(allStories);
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

    let list = allStories.filter((s) => !junkIdSet.has(String(s.id)));

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
      if (junkIdSet.has(String(s.id))) continue;
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

  function introUp() {
    return els["intro-screen"] && !els["intro-screen"].hidden;
  }

  function showRundownView() {
    // The title screen is home: it carries no data-page and keeps its own
    // look. Only re-theme once the intro is dismissed and the picker shows.
    if (!introUp()) setPage("picker");
    if (els["rundown-view"]) els["rundown-view"].hidden = false;
    if (els["edition-view"]) els["edition-view"].hidden = true;
  }

  function showEditionView() {
    if (!introUp()) setPage("board");
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

    root.innerHTML = visibleStories
      .map((s) => {
        const ca =
          s.entities && s.entities.is_canadian
            ? '<span class="tag tag-ca" title="Canadian">🇨🇦 CA</span>'
            : "";
        const clip = SSClips.clipCountBadge(s.clips);
        const sid = SSLoadout.storyId(s);
        const selected = SSLoadout.has(sid) ? " selected" : "";
        const debate = s.debate
          ? `<p class="card-debate">${SSClips.escapeHtml(s.debate)}</p>`
          : "";
        const customDel = s._custom
          ? `<button type="button" class="custom-delete" data-custom-id="${SSClips.escapeAttr(
              s.id
            )}">DELETE</button>`
          : "";
        return `<article class="card story-card${s.is_backup ? " is-backup" : ""}${
          s._custom ? " custom" : ""
        }${selected}" role="listitem" tabindex="0" data-id="${SSClips.escapeAttr(sid)}">
          <div class="card-top">
            <span class="tag cat">${SSClips.escapeHtml(s.category || "")}</span>
            <span class="score-pill">${s.score === "" ? "—" : Number(s.score || 0).toFixed(0)}</span>
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
            ${customDel}
          </div>
          <div class="card-actions">
            <button type="button" class="btn" data-act="detail" data-id="${SSClips.escapeAttr(s.id)}">Detail</button>
            <button type="button" class="btn btn-danger" data-act="junk" data-id="${SSClips.escapeAttr(s.id)}">JUNK</button>
          </div>
        </article>`;
      })
      .join("");

    // Production behavior: clicking the card toggles it in the loadout.
    root.querySelectorAll(".story-card").forEach((card) => {
      card.addEventListener("click", (e) => {
        if (e.target.closest("button") || e.target.closest("a")) return;
        SSLoadout.toggleStory(card.dataset.id);
        renderCards();
      });
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.target.closest("button")) {
          SSLoadout.toggleStory(card.dataset.id);
          renderCards();
        }
      });
    });
    root.querySelectorAll("button[data-act]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        if (btn.dataset.act === "detail") openDetail(id);
        if (btn.dataset.act === "junk") junkStoryById(id);
      });
    });
    root.querySelectorAll(".custom-delete").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteCustomStory(btn.dataset.customId);
      });
    });
  }

  // Called by the loadout panel when an item's X button removes a story,
  // so the card's selected state refreshes.
  window.SSLoadoutCardsChanged = function () {
    renderCards();
  };

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
        <button type="button" class="btn btn-danger" id="detail-junk">JUNK</button>
      </div>
    `;
    const addBtn = document.getElementById("detail-add");
    if (addBtn) {
      const sid = SSLoadout.storyId(s);
      const syncDetailAddLabel = () => {
        addBtn.textContent = SSLoadout.has(sid) ? "✓ In loadout" : "+ Loadout";
      };
      syncDetailAddLabel();
      addBtn.addEventListener("click", () => {
        SSLoadout.toggleStory(sid);
        syncDetailAddLabel();
        renderCards();
      });
    }
    const junkBtn = document.getElementById("detail-junk");
    if (junkBtn) junkBtn.addEventListener("click", () => junkStoryById(s.id));
    els["detail-dialog"].showModal();
  }

  async function refreshJunkIds() {
    junkIdSet = await SSStorage.getJunkIds();
    return junkIdSet;
  }

  function removeJunkFromLoadout() {
    if (!SSLoadout || !SSLoadout.getSelectedStories) return false;
    const before = SSLoadout.count();
    SSLoadout.getSelectedStories().forEach((s) => {
      if (junkIdSet.has(String(s.id)))
        SSLoadout.removeFromPrep(SSLoadout.storyId(s), true);
    });
    return SSLoadout.count() !== before;
  }

  async function junkStoryById(id) {
    const story = findStory(id);
    if (!story || junkIdSet.has(String(id))) return;
    await SSStorage.junkStory(story);
    if (SSLoadout) SSLoadout.removeFromPrep(SSLoadout.storyId(story));
    await refreshJunkIds();
    if (els["detail-dialog"] && els["detail-dialog"].open) els["detail-dialog"].close();
    buildRundownIndex();
    if (activeEdition) await applyFilters();
    else renderRundownPicker();
    if (SSLoadout && SSLoadout.render) SSLoadout.render();
    showToast("Sent to Junk");
  }

  function formatJunkDate(iso) {
    const date = new Date(iso);
    return Number.isNaN(date.getTime())
      ? "unknown date"
      : date.toLocaleString("en-CA", { timeZone: "America/Toronto" }) + " ET";
  }

  function renderJunkList() {
    if (!els["junk-list"]) return;
    SSStorage.listJunk().then((rows) => {
      if (!rows.length) {
        els["junk-list"].innerHTML = '<p class="empty-state">Junk is empty. Deleted stories wait here 7 days.</p>';
        return;
      }
      const now = Date.now();
      els["junk-list"].innerHTML = rows.map((row) => {
        const story = row.story || {};
        const deleted = new Date(row.deletedAt).getTime();
        const remaining = Number.isNaN(deleted)
          ? ""
          : Math.max(0, Math.ceil((deleted + 7 * 24 * 60 * 60 * 1000 - now) / (24 * 60 * 60 * 1000)));
        return `<article class="junk-row" data-id="${SSClips.escapeAttr(row.id)}">
          <div class="junk-row-copy">
            <h3>${SSClips.escapeHtml(story.title || row.id)}</h3>
            <p>Deleted ${SSClips.escapeHtml(formatJunkDate(row.deletedAt))}${remaining !== "" ? " · " + remaining + " day" + (remaining === 1 ? "" : "s") + " remaining" : ""}</p>
          </div>
          <div class="junk-row-actions">
            <button type="button" class="btn btn-primary" data-junk-act="restore" data-id="${SSClips.escapeAttr(row.id)}">RESTORE</button>
            <button type="button" class="btn btn-danger" data-junk-act="delete" data-id="${SSClips.escapeAttr(row.id)}">DELETE FOREVER</button>
          </div>
        </article>`;
      }).join("");
      els["junk-list"].querySelectorAll("button[data-junk-act]").forEach((btn) => {
        btn.addEventListener("click", () => {
          if (btn.dataset.junkAct === "restore") restoreJunkStory(btn.dataset.id);
          if (btn.dataset.junkAct === "delete") deleteJunkForever(btn.dataset.id);
        });
      });
    }).catch((err) => console.warn("[junk] list failed", err));
  }

  async function deleteCustomStory(cid) {
    const story = allStories.find((s) => String(s.id) === String(cid));
    if (story) SSLoadout.removeFromPrep(SSLoadout.storyId(story), true);
    await SSStorage.deleteCustomStory(cid);
    allStories = allStories.filter((s) => String(s.id) !== String(cid));
    SSLoadout.setStories(allStories);
    await SSSearch.rebuild(allStories);
    updateStatus();
    buildRundownIndex();
    if (activeEdition) await applyFilters();
    else renderRundownPicker();
    SSLoadout.render();
    showToast("CUSTOM STORY DELETED");
  }

  async function restoreJunkStory(id) {
    const story = await SSStorage.restoreJunk(id);
    if (story && !findStory(story.id)) {
      allStories.unshift(story);
      SSLoadout.setStories(allStories);
      await SSSearch.rebuild(allStories);
    }
    await refreshJunkIds();
    buildRundownIndex();
    if (activeEdition) await applyFilters();
    else renderRundownPicker();
    renderJunkList();
    showToast("Restored from Junk");
  }

  async function deleteJunkForever(id) {
    await SSStorage.deleteJunk(id);
    await refreshJunkIds();
    renderJunkList();
    buildRundownIndex();
    if (activeEdition) await applyFilters();
    else renderRundownPicker();
  }

  function brandLabel() {
    const brand = document.documentElement.getAttribute("data-brand") || "jaystation";
    return brand === "jaystation" ? "Jaystation · Radio Prep" : "Daily Goods · Radio Prep";
  }

  function brandShort() {
    const brand = document.documentElement.getAttribute("data-brand") || "jaystation";
    return brand === "jaystation" ? "JS" : "DG";
  }

  function brandLong() {
    const brand = document.documentElement.getAttribute("data-brand") || "jaystation";
    return brand === "jaystation" ? "JAYSTATION" : "DAILY GOODS";
  }

  function syncThemeButtons() {
    const theme = document.documentElement.getAttribute("data-theme") || "night";
    const brand = document.documentElement.getAttribute("data-brand") || "jaystation";
    if (els["btn-theme"]) els["btn-theme"].textContent = theme === "night" ? "DAY" : "NIGHT";
    if (els["brand-label"]) els["brand-label"].textContent = brandLabel();
    if (els["intro-theme"]) {
      els["intro-theme"].textContent = theme === "night" ? "DAY MODE" : "NIGHT MODE";
    }
    if (els["intro-theme-opt"]) {
      els["intro-theme-opt"].textContent = "THEME: " + (theme === "night" ? "DAY" : "NIGHT");
    }
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
    syncPageMeta();
  }

  /* Per-page duo palettes: home has no data-page (untouched); the rundown
     picker, story board, and credits each re-theme within their own duo. */
  function setPage(page) {
    const html = document.documentElement;
    if (page) html.setAttribute("data-page", page);
    else html.removeAttribute("data-page");
    syncPageMeta();
  }

  function syncPageMeta() {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) return;
    const theme =
      document.documentElement.getAttribute("data-theme") || "night";
    const page =
      document.documentElement.getAttribute("data-page") || "home";
    const colors = {
      home: { night: "#012641", day: "#F7E6D2" },
      picker: { night: "#211138", day: "#FDDFCB" },
      board: { night: "#012641", day: "#FBC3D8" },
      credits: { night: "#24080B", day: "#F7E6D2" },
    };
    meta.setAttribute(
      "content",
      ((colors[page] || colors.home)[theme] || colors.home.night)
    );
  }

  async function applyThemeSettings() {
    const theme = await SSStorage.loadSetting("theme", "night");
    const brand = "jaystation"; // Jaystation is the standard; no brand switch
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.setAttribute("data-brand", brand);
    syncThemeButtons();
    syncPageMeta();
  }

  async function toggleTheme() {
    const cur = document.documentElement.getAttribute("data-theme") || "night";
    const next = cur === "night" ? "day" : "night";
    await SSStorage.saveSetting("theme", next);
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

    if (els["btn-junk-folder"]) {
      els["btn-junk-folder"].addEventListener("click", () => {
        renderJunkList();
        if (els["junk-dialog"]) els["junk-dialog"].showModal();
      });
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

    // ADD STORY: exact copy of the original's functionality.
    function showAddStory() {
      const form = els["custom-form"];
      if (form) form.reset();
      const today = new Date().toLocaleDateString("en-CA", { timeZone: "America/Toronto" });
      const dateInput = form && form.elements.namedItem("cdate");
      const slotInput = form && form.elements.namedItem("cslot");
      if (dateInput) dateInput.value = (activeEdition && activeEdition.date) || today;
      if (slotInput) slotInput.value = (activeEdition && activeEdition.slot) || "am";
      if (els["custom-dialog"]) els["custom-dialog"].showModal();
      const titleInput = document.getElementById("addTitle");
      if (titleInput) titleInput.focus();
    }
    if (els["btn-custom"]) els["btn-custom"].addEventListener("click", showAddStory);
    if (els["btn-custom-picker"]) els["btn-custom-picker"].addEventListener("click", showAddStory);

    if (els["custom-form"]) {
      els["custom-dialog"].addEventListener("close", async () => {
        if (els["custom-dialog"].returnValue !== "ok") return;
        const fd = new FormData(els["custom-form"]);
        const title = String(fd.get("title") || "").trim();
        const url = String(fd.get("url") || "").trim();
        const angle = String(fd.get("angle") || "").trim();
        const bulletsRaw = String(fd.get("bullets") || "").trim();
        const bullets = bulletsRaw ? bulletsRaw.split("\n").map((b) => b.trim()).filter(Boolean) : [];
        const cdate = String(fd.get("cdate") || "").trim();
        const cslot = String(fd.get("cslot") || "am") === "pm" ? "pm" : "am";
        if (!title) { showToast("TITLE REQUIRED"); return; }
        if (!cdate) { showToast("DATE REQUIRED"); return; }
        const id = "custom-" + Date.now().toString(36);
        const story = {
          id,
          _custom: true,
          title,
          url,
          date: cdate,
          slot: cslot,
          category: "ADDED STORIES",
          angle,
          bullets,
          debate: "",
          score: "",
          source: "",
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
        SSLoadout.setStories(allStories);
        await SSSearch.rebuild(allStories);
        updateStatus();
        buildRundownIndex();
        // Like the original: never navigate away. If the story belongs to the
        // edition on screen, re-render so it appears; on the picker, refresh
        // the rundown list.
        if (activeEdition && activeEdition.date === story.date && activeEdition.slot === story.slot) {
          applyFilters();
        } else if (!activeEdition) {
          renderRundownPicker();
        }
        showToast("CUSTOM STORY ADDED");
      });
    }

    // Loadout panel: production button set (SELECT ALL = copy, like the original).
    if (els["btn-selall-loadout"]) {
      els["btn-selall-loadout"].addEventListener("click", () => {
        SSLoadout.selectAllText();
      });
    }
    if (els["btn-copy-loadout"]) {
      els["btn-copy-loadout"].addEventListener("click", () => {
        SSLoadout.copyPrep();
      });
    }
    if (els["btn-print-loadout"]) {
      els["btn-print-loadout"].addEventListener("click", () => {
        SSLoadout.printPrep();
      });
    }
    if (els["btn-email-loadout"]) {
      els["btn-email-loadout"].addEventListener("click", () => {
        SSLoadout.emailPrep();
      });
    }
    if (els["btn-clear-loadout"]) {
      els["btn-clear-loadout"].addEventListener("click", () => {
        SSLoadout.clearPrep();
        renderCards();
      });
    }
    // Browser toolbar SELECT ALL: adds every currently visible story.
    if (els["btn-select-all"]) {
      els["btn-select-all"].addEventListener("click", () => {
        SSLoadout.selectAllVisible(visibleStories);
        renderCards();
      });
    }
    if (els["btn-close-loadout"]) {
      els["btn-close-loadout"].addEventListener("click", () => {
        closeLoadoutDrawer(false);
      });
    }
    if (els["btn-loadout"]) {
      els["btn-loadout"].addEventListener("click", () => {
        const pane = els["loadout-pane"];
        if (!pane) return;
        if (window.matchMedia("(max-width: 960px)").matches) {
          if (pane.classList.contains("open")) closeLoadoutDrawer(false);
          else openLoadoutDrawer();
        } else {
          pane.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    }
    // Mobile drawer: the OS/browser back gesture should close the drawer,
    // not navigate away from the board. Push a history entry on open and
    // close the drawer on popstate instead of leaving the page.
    let drawerHistoryPushed = false;
    function openLoadoutDrawer() {
      const pane = els["loadout-pane"];
      if (!pane) return;
      pane.classList.add("open");
      if (!drawerHistoryPushed) {
        try {
          window.history.pushState({ ssnDrawer: "loadout" }, "");
          drawerHistoryPushed = true;
        } catch (err) {
          /* history unavailable */
        }
      }
    }
    function closeLoadoutDrawer(viaPop) {
      const pane = els["loadout-pane"];
      if (!pane || !pane.classList.contains("open")) return;
      pane.classList.remove("open");
      if (!viaPop && drawerHistoryPushed) {
        drawerHistoryPushed = false;
        window.history.back();
      }
    }
    window.addEventListener("popstate", () => {
      const pane = els["loadout-pane"];
      if (pane && pane.classList.contains("open")) {
        pane.classList.remove("open");
        drawerHistoryPushed = false;
      }
    });

    window.addEventListener("online", updateStatus);
    window.addEventListener("offline", updateStatus);
  }

  function registerSw() {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker
      .register("./sw.js?v=6")
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
      await SSStorage.purgeJunkOlderThan(7);
      await refreshJunkIds();
      await bootstrapStories();
      // Working loadout restores from this browser's localStorage
      // (auto-saved after every change; per-user, never shared).
      SSLoadout.restore();
      removeJunkFromLoadout();
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
