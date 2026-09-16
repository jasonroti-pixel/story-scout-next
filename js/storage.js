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
  };
})(window);
