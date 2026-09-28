/**
 * Story Scout Next — Sortable loadout (notes / backup / save / load / prep sheet).
 *
 * PER-USER ISOLATION: the working loadout lives ONLY in this browser's
 * localStorage (key below). It is never placed in the URL, never sent to a
 * server, and never synced anywhere. Every person who opens the link gets
 * their own independent loadout in their own browser.
 */
(function (global) {
  "use strict";

  // Working loadout storage: this browser only. Nothing leaves the device.
  const LS_KEY = "ssn-v2-loadout-v1";

  let items = []; // { id, notes, isBackup }
  let sortable = null;
  let storyById = new Map();

  function setStoryIndex(stories) {
    storyById = new Map((stories || []).map((s) => [String(s.id), s]));
  }

  function getItems() {
    return items.slice();
  }

  function setItems(next) {
    items = (next || []).map((it) => ({
      id: String(it.id),
      notes: it.notes || "",
      isBackup: !!it.isBackup,
    }));
    persist();
    render();
  }

  // Write the working loadout to this browser's localStorage after EVERY
  // mutation, so it survives reloads, navigation, and app restarts.
  function persist() {
    try {
      global.localStorage.setItem(
        LS_KEY,
        JSON.stringify({ items: items, savedAt: new Date().toISOString() })
      );
    } catch (err) {
      console.warn("[loadout] persist failed", err);
    }
  }

  // Restore the working loadout from this browser's localStorage.
  // Call AFTER setStoryIndex so custom stories resolve.
  function restore() {
    let raw = null;
    try {
      raw = global.localStorage.getItem(LS_KEY);
    } catch (err) {
      console.warn("[loadout] restore failed", err);
      return;
    }
    if (!raw) return;
    try {
      const data = JSON.parse(raw);
      if (data && Array.isArray(data.items)) {
        items = data.items.map((it) => ({
          id: String(it.id),
          notes: it.notes || "",
          isBackup: !!it.isBackup,
        }));
      }
    } catch (err) {
      console.warn("[loadout] restore parse failed", err);
    }
    render();
  }

  function addStory(id) {
    id = String(id);
    if (items.some((it) => it.id === id)) return false;
    items.push({ id, notes: "", isBackup: false });
    persist();
    render();
    return true;
  }

  function removeStory(id) {
    const before = items.length;
    items = items.filter((it) => it.id !== String(id));
    if (items.length !== before) {
      persist();
      render();
      return true;
    }
    return false;
  }

  // Production parity: one tap toggles the story in/out of the loadout.
  function toggleStory(id) {
    id = String(id);
    if (items.some((it) => it.id === id)) {
      removeStory(id);
      return "removed";
    }
    addStory(id);
    return "added";
  }

  function toggleBackup(id) {
    const it = items.find((x) => x.id === String(id));
    if (it) {
      it.isBackup = !it.isBackup;
      persist();
      render();
    }
  }

  function setNotes(id, notes) {
    const it = items.find((x) => x.id === String(id));
    if (it) {
      it.notes = notes;
      persist();
    }
  }

  function clear() {
    items = [];
    persist();
    render();
  }

  function updateCountBadge() {
    const badge = document.getElementById("loadout-count");
    if (badge) badge.textContent = String(items.length);
    const btn = document.getElementById("btn-loadout");
    if (btn) btn.setAttribute("aria-label", "Loadout, " + items.length + " stories");
  }

  function render() {
    updateCountBadge();
    const list = document.getElementById("loadout-list");
    if (!list) return;
    if (!items.length) {
      list.innerHTML =
        '<li class="hint">Tap + Loadout on any story to build your rundown here.<br><span class="lo-local">Loadout lives in this browser only — nobody else sees it.</span></li>';
      return;
    }
    list.innerHTML = items
      .map((it, idx) => {
        const s = storyById.get(it.id);
        const title = s ? s.title : "(missing story " + it.id + ")";
        const cat = s ? s.category : "";
        return `<li class="loadout-item card${it.isBackup ? " is-backup" : ""}" data-id="${SSClips.escapeAttr(it.id)}">
          <span class="lo-title">${idx + 1}. ${SSClips.escapeHtml(title)}</span>
          <span class="lo-cat">${SSClips.escapeHtml(cat)}${it.isBackup ? " · BACKUP" : ""}</span>
          <label>Notes
            <input class="input lo-notes" data-id="${SSClips.escapeAttr(it.id)}" value="${SSClips.escapeAttr(it.notes)}" />
          </label>
          <div class="lo-actions">
            <button type="button" class="btn btn-warning" data-act="backup" data-id="${SSClips.escapeAttr(it.id)}">★ Backup</button>
            <button type="button" class="btn btn-danger" data-act="remove" data-id="${SSClips.escapeAttr(it.id)}">Remove</button>
          </div>
        </li>`;
      })
      .join("");

    list.querySelectorAll(".lo-notes").forEach((input) => {
      input.addEventListener("change", () => setNotes(input.dataset.id, input.value));
    });
    list.querySelectorAll("button[data-act]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        if (btn.dataset.act === "backup") toggleBackup(id);
        if (btn.dataset.act === "remove") removeStory(id);
      });
    });

    if (sortable) sortable.destroy();
    sortable = Sortable.create(list, {
      animation: 120,
      draggable: ".loadout-item",
      onEnd: () => {
        const order = Array.from(list.querySelectorAll(".loadout-item")).map((el) => el.dataset.id);
        items = order.map((id) => items.find((it) => it.id === id)).filter(Boolean);
        persist();
      },
    });
  }

  function storyDateLabel(s) {
    return s && s.date ? s.date : "UNDATED";
  }

  // Production-parity plain-text export format:
  // header block, date groups newest-first, numbered stories with
  // category, angle, bullets, debate, source.
  function buildPrepText() {
    const groups = new Map();
    items.forEach((it, idx) => {
      const s = storyById.get(it.id) || {};
      const key = storyDateLabel(s);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push({ it, s, order: idx });
    });
    const groupKeys = Array.from(groups.keys()).sort().reverse();
    const lines = [];
    lines.push("════════════════════════════════════════════════════════════");
    lines.push("DAILY GOODS — STORY LOADOUT (" + items.length + " STORIES)");
    lines.push(
      "Prepared: " +
        new Date().toLocaleString("en-CA", { timeZone: "America/Toronto" }) +
        " ET · Segment-ready story texts for the show"
    );
    lines.push("════════════════════════════════════════════════════════════");
    lines.push("");
    let n = 0;
    groupKeys.forEach((key) => {
      const group = groups.get(key);
      let label = key;
      try {
        label =
          new Date(key + "T12:00:00").toLocaleDateString("en-CA", {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
            timeZone: "America/Toronto",
          }).toUpperCase() || key;
      } catch (e) {
        /* keep raw key */
      }
      lines.push(label + " (" + group.length + (group.length === 1 ? " STORY" : " STORIES") + ")");
      lines.push("");
      group
        .sort((a, b) => a.order - b.order)
        .forEach(({ it, s }) => {
          n += 1;
          lines.push(
            n +
              ". " +
              (s.category || "") +
              " — " +
              (s.title || it.id) +
              (it.isBackup ? " (BACKUP)" : "")
          );
          if (s.angle) lines.push("   Angle: " + s.angle);
          (s.bullets || []).forEach((b) => lines.push("   • " + b));
          if (s.debate) lines.push("   Debate: " + s.debate);
          if (s.source) lines.push("   Source: " + s.source);
          if (it.notes) lines.push("   Notes: " + it.notes);
          lines.push("");
        });
    });
    return lines.join("\n");
  }

  function copyPrepText() {
    const text = buildPrepText();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(
        () => true,
        () => fallbackCopy(text)
      );
    }
    return Promise.resolve(fallbackCopy(text));
  }

  function fallbackCopy(text) {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch (e) {
      return false;
    }
  }

  function emailPrepText() {
    const text = buildPrepText();
    const subject = "Daily Goods — Story Loadout (" + items.length + ")";
    global.location.href =
      "mailto:?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(text);
  }

  function buildPrepHtml(brandLabel) {
    const lines = items.map((it, idx) => {
      const s = storyById.get(it.id) || {};
      const bullets = (s.bullets || []).map((b) => `<li>${SSClips.escapeHtml(b)}</li>`).join("");
      return `<section class="prep-item${it.isBackup ? " backup" : ""}">
        <h2>${idx + 1}. ${SSClips.escapeHtml(s.title || it.id)}${it.isBackup ? " (BACKUP)" : ""}</h2>
        <p><strong>${SSClips.escapeHtml(s.category || "")}</strong> · ${SSClips.escapeHtml(s.source || "")}</p>
        <p><em>Angle:</em> ${SSClips.escapeHtml(s.angle || "")}</p>
        <ul>${bullets}</ul>
        <p><em>Debate:</em> <span class="detail-debate">${SSClips.escapeHtml(s.debate || "")}</span></p>
        ${it.notes ? `<p><em>Notes:</em> ${SSClips.escapeHtml(it.notes)}</p>` : ""}
        ${s.url ? `<p><a href="${SSClips.escapeAttr(s.url)}" target="_blank" rel="noopener">Source</a></p>` : ""}
      </section>`;
    });
    return `<h1>${SSClips.escapeHtml(brandLabel || "Story Scout")} — Prep Sheet</h1>
      <p>${new Date().toLocaleString("en-CA", { timeZone: "America/Toronto" })} ET · ${items.length} segments</p>
      ${lines.join("") || "<p>Loadout empty.</p>"}`;
  }

  async function save() {
    return SSStorage.saveLoadout({ id: "default", name: "Default", items });
  }

  async function load() {
    const row = await SSStorage.loadLoadout("default");
    if (row && row.items) setItems(row.items);
    return row;
  }

  global.SSLoadout = {
    setStoryIndex,
    getItems,
    setItems,
    addStory,
    removeStory,
    toggleStory,
    toggleBackup,
    clear,
    render,
    persist,
    restore,
    buildPrepText,
    copyPrepText,
    emailPrepText,
    buildPrepHtml,
    save,
    load,
  };
})(window);
