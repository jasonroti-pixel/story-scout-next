/**
 * Story Scout Next — Dexie (IndexedDB) persistence.
 */
(function (global) {
  "use strict";

  const db = new Dexie("StoryScoutNext");
  db.version(1).stores({
    stories: "id, date, slot, category, score, is_backup",
    meta: "key",
    loadouts: "id, name, updatedAt",
    settings: "key",
  });
  db.version(2).stores({
    junk: "id, deletedAt",
  });

  async function saveStories(stories, meta) {
    await db.transaction("rw", db.stories, db.meta, async () => {
      await db.stories.clear();
      if (stories && stories.length) {
        await db.stories.bulkPut(stories);
      }
      await db.meta.put({
        key: "lastSync",
        value: meta || {
          syncedAt: new Date().toISOString(),
          count: (stories || []).length,
        },
      });
    });
  }

  async function loadStories() {
    return db.stories.toArray();
  }

  async function getMeta(key) {
    const row = await db.meta.get(key);
    return row ? row.value : null;
  }

  async function putMeta(key, value) {
    await db.meta.put({ key, value });
  }

  async function saveSetting(key, value) {
    await db.settings.put({ key, value });
  }

  async function loadSetting(key, fallback) {
    const row = await db.settings.get(key);
    return row ? row.value : fallback;
  }

  async function saveLoadout(loadout) {
    const row = {
      id: loadout.id || "default",
      name: loadout.name || "Default",
      items: loadout.items || [],
      updatedAt: new Date().toISOString(),
    };
    await db.loadouts.put(row);
    return row;
  }

  async function loadLoadout(id) {
    return db.loadouts.get(id || "default");
  }

  async function listLoadouts() {
    return db.loadouts.orderBy("updatedAt").reverse().toArray();
  }

  async function upsertCustomStory(story) {
    await db.stories.put(story);
  }

  async function junkStory(story) {
    if (!story || story.id == null) return;
    await db.junk.put({
      id: String(story.id),
      story,
      deletedAt: new Date().toISOString(),
    });
  }

  async function listJunk() {
    return db.junk.orderBy("deletedAt").reverse().toArray();
  }

  async function restoreJunk(id) {
    const key = String(id);
    return db.transaction("rw", db.junk, async () => {
      const row = await db.junk.get(key);
      if (!row) return null;
      await db.junk.delete(key);
      return row.story || null;
    });
  }

  async function deleteJunk(id) {
    await db.junk.delete(String(id));
  }

  async function purgeJunkOlderThan(days = 7) {
    const ageDays = Number.isFinite(Number(days)) ? Number(days) : 7;
    const cutoff = new Date(Date.now() - ageDays * 24 * 60 * 60 * 1000).toISOString();
    return db.transaction("rw", db.junk, async () => {
      const ids = await db.junk.where("deletedAt").below(cutoff).primaryKeys();
      if (ids.length) await db.junk.bulkDelete(ids);
      return ids.length;
    });
  }

  async function isJunked(id) {
    return !!(await db.junk.get(String(id)));
  }

  async function getJunkIds() {
    const rows = await db.junk.toCollection().primaryKeys();
    return new Set(rows.map(String));
  }

  global.SSStorage = {
    db,
    saveStories,
    loadStories,
    getMeta,
    putMeta,
    saveSetting,
    loadSetting,
    saveLoadout,
    loadLoadout,
    listLoadouts,
    upsertCustomStory,
    junkStory,
    listJunk,
    restoreJunk,
    deleteJunk,
    purgeJunkOlderThan,
    isJunked,
    getJunkIds,
  };
})(window);
