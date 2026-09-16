/**
 * Story Scout Next — Orama full-text search index.
 */
(function (global) {
  "use strict";

  let db = null;

  function getOrama() {
    const O = global.Orama || global.orama || null;
    if (O && typeof O.create === "function") return O;
    return null;
  }

  function whenReady(timeoutMs) {
    if (getOrama()) return Promise.resolve(getOrama());
    return new Promise((resolve) => {
      const t = setTimeout(() => resolve(getOrama()), timeoutMs || 2500);
      global.addEventListener(
        "orama-ready",
        () => {
          clearTimeout(t);
          resolve(getOrama());
        },
        { once: true }
      );
    });
  }

  async function rebuild(stories) {
    const O = getOrama();
    if (!O || !O.create || !O.insert || !O.search) {
      db = null;
      console.warn("[search] Orama CDN not available; using fallback filter");
      return;
    }
    db = await O.create({
      schema: {
        id: "string",
        title: "string",
        angle: "string",
        summary: "string",
        category: "string",
        source: "string",
        debate: "string",
        bulletsText: "string",
      },
    });
    for (const s of stories || []) {
      await O.insert(db, {
        id: String(s.id),
        title: s.title || "",
        angle: s.angle || "",
        summary: s.summary || "",
        category: s.category || "",
        source: s.source || "",
        debate: s.debate || "",
        bulletsText: (s.bullets || []).join(" "),
      });
    }
  }

  async function query(text, limit) {
    const O = getOrama();
    if (!db || !O || !text || !String(text).trim()) return null;
    const result = await O.search(db, {
      term: String(text).trim(),
      limit: limit || 100,
      tolerance: 1,
      properties: ["title", "angle", "summary", "category", "source", "debate", "bulletsText"],
    });
    return (result.hits || []).map((h) => h.document.id);
  }

  function fallbackFilter(stories, text) {
    const q = String(text || "").trim().toLowerCase();
    if (!q) return stories;
    return stories.filter((s) => {
      const blob = [
        s.title,
        s.angle,
        s.summary,
        s.category,
        s.source,
        s.debate,
        (s.bullets || []).join(" "),
      ]
        .join(" ")
        .toLowerCase();
      return blob.includes(q);
    });
  }

  global.SSSearch = { rebuild, query, fallbackFilter, whenReady };
})(window);
