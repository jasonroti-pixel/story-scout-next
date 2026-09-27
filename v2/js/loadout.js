/**
 * Story Scout Next — Sortable loadout (notes / backup / save / load / prep sheet).
 */
(function (global) {
  "use strict";

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
    render();
  }

  function addStory(id) {
    id = String(id);
    if (items.some((it) => it.id === id)) return;
    items.push({ id, notes: "", isBackup: false });
    render();
  }

  function removeStory(id) {
    items = items.filter((it) => it.id !== String(id));
    render();
  }

  function toggleBackup(id) {
    const it = items.find((x) => x.id === String(id));
    if (it) {
      it.isBackup = !it.isBackup;
      render();
    }
  }

  function setNotes(id, notes) {
    const it = items.find((x) => x.id === String(id));
    if (it) it.notes = notes;
  }

  function clear() {
    items = [];
    render();
  }

  function render() {
    const list = document.getElementById("loadout-list");
    if (!list) return;
    if (!items.length) {
      list.innerHTML = '<li class="hint">Drop stories here from Add → Loadout</li>';
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
      },
    });
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
    toggleBackup,
    clear,
    render,
    buildPrepHtml,
    save,
    load,
  };
})(window);
