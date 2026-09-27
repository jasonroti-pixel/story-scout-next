/**
 * Story Scout Next v2 — Peak Arcade presentation layer.
 * Visual only: pixel scenes, hidden-Nico easter eggs, end credits.
 * Touches no app state (stories, loadout, filters stay in app.js).
 */
(function () {
  "use strict";

  const EGG_KEY = "ssn-v2:nico-found";
  const EGGS = ["city", "trail", "harbor", "alley"];
  const sceneCache = new Map();

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  // ---------- toast (own timer; app.js keeps its own) ----------
  let toastTimer = null;
  function toast(msg) {
    const t = document.getElementById("toast");
    if (!t) return;
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      t.hidden = true;
    }, 2600);
  }

  // ---------- scenes ----------
  function loadScene(name) {
    if (!sceneCache.has(name)) {
      sceneCache.set(
        name,
        fetch("assets/px/scene-" + name + ".svg")
          .then((r) => (r.ok ? r.text() : ""))
          .catch(() => "")
      );
    }
    return sceneCache.get(name);
  }

  async function mountScene(el) {
    const name = el.dataset.scene;
    if (!name || el.dataset.mounted === name) return;
    const svg = await loadScene(name);
    if (el.dataset.scene !== name) return; // switched while loading
    el.innerHTML = svg;
    el.dataset.mounted = name;
    el.querySelectorAll(".nico-egg").forEach(wireEgg);
  }

  function mountAll(root) {
    (root || document).querySelectorAll(".px-scene[data-scene]").forEach(mountScene);
  }

  // App backdrop follows the view: trail for the rundown picker, harbour for an edition.
  function syncAppScene() {
    const scene = document.getElementById("app-scene");
    const shell = document.getElementById("app-shell");
    const rundown = document.getElementById("rundown-view");
    if (!scene || !shell) return;
    scene.hidden = shell.hidden;
    const next = rundown && !rundown.hidden ? "trail" : "harbor";
    if (scene.dataset.scene !== next) {
      scene.dataset.scene = next;
      mountScene(scene);
    }
  }

  // ---------- hidden Nico ----------
  function foundSet() {
    try {
      return new Set(JSON.parse(localStorage.getItem(EGG_KEY) || "[]"));
    } catch (_) {
      return new Set();
    }
  }

  function saveFound(set) {
    try {
      localStorage.setItem(EGG_KEY, JSON.stringify(Array.from(set)));
    } catch (_) {
      /* private mode: progress just isn't remembered */
    }
  }

  function wireEgg(g) {
    g.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = g.dataset.egg;
      const set = foundSet();
      const isNew = !set.has(id);
      set.add(id);
      saveFound(set);
      g.classList.remove("found");
      void g.getBoundingClientRect();
      g.classList.add("found");
      const n = EGGS.filter((x) => set.has(x)).length;
      if (!isNew) {
        toast("Nico says hi again! (" + n + "/" + EGGS.length + ")");
      } else if (n >= EGGS.length) {
        toast("ALL " + EGGS.length + " NICOS FOUND! Rolling credits…");
        setTimeout(openCredits, 1400);
      } else {
        toast("You found Nico! " + n + "/" + EGGS.length + " hidden Nicos");
      }
    });
  }

  // ---------- end credits ----------
  const CREDITS = [
    ["STARRING", "NICO"],
    ["AS HIMSELF", "A VERY GOOD BOY"],
    ["BALL WRANGLER", "NICO"],
    ["PRESENTED BY", "THE DAILY GOODS"],
    ["ON AIR", "JAYSTATION"],
    ["STORY SCOUTING", "THE INGEST PIPELINE"],
    ["RUNDOWN DESIGN", "THE PREP DESK"],
    ["PIXEL ART", "PEAK ARCADE DEPT."],
    ["PALETTE", "DEEP SPACE BLUE · BURGUNDY · INDIGO VELVET"],
    ["", "ANTIQUE WHITE · SANDY BROWN · RASPBERRY RED"],
    ["FILMED ON LOCATION", "TORONTO"],
    ["SPECIAL THANKS", "THE RED & BLUE BALL"],
    ["NO BALLS WERE LOST", "IN THE MAKING OF THIS BOARD"],
  ];

  const TIMELINE = [
    [16000, "is-arriving"],
    [22000, "is-parked"],
    [23400, "is-throwing"],
    [24000, "is-jumping"],
    [24600, "is-caught"],
    [25200, "-is-jumping"],
    [26400, "is-ended"],
  ];

  let timers = [];
  let lastFocus = null;

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  function layer(cls, name) {
    return (
      '<div class="cr-layer ' + cls + '">' +
      '<div class="px-scene" data-scene="' + name + '"></div>' +
      '<div class="px-scene" data-scene="' + name + '"></div></div>'
    );
  }

  function buildCredits(root) {
    const rows = CREDITS.map(
      ([k, v]) => (k ? "<dt>" + esc(k) + "</dt>" : "") + "<dd>" + esc(v) + "</dd>"
    ).join("");
    root.innerHTML =
      '<button type="button" class="btn cr-skip" data-cr="skip">SKIP ▶▶</button>' +
      '<div class="cr-stage" aria-hidden="true">' +
      '<div class="px-scene cr-sky" data-scene="credits-sky"></div>' +
      layer("cr-far", "credits-far") +
      layer("cr-mid", "credits-mid") +
      '<img class="cr-sprite cr-house" src="assets/px/farmhouse.svg" alt="" />' +
      layer("cr-ground", "credits-ground") +
      '<div class="cr-nico">' +
      '<img class="f-run f-run0" src="assets/px/nico-run0.svg" alt="" />' +
      '<img class="f-run f-run1" src="assets/px/nico-run1.svg" alt="" />' +
      '<img class="f-run f-run2" src="assets/px/nico-run2.svg" alt="" />' +
      '<img class="f-run f-run3" src="assets/px/nico-run3.svg" alt="" />' +
      '<img class="f-sit" src="assets/px/nico-sit.svg" alt="" />' +
      '<img class="f-jump" src="assets/px/nico-jump.svg" alt="" />' +
      '<img class="cr-held" src="assets/px/ball.svg" alt="" />' +
      "</div>" +
      '<div class="cr-ball-x"><div class="cr-ball-y"><img src="assets/px/ball.svg" alt="" /></div></div>' +
      "</div>" +
      '<div class="cr-roll"><div class="cr-roll-inner">' +
      "<h2>STORY SCOUT</h2>" +
      '<p class="plate-kicker">V2 · PEAK ARCADE EDITION</p>' +
      "<dl>" + rows + "</dl></div></div>" +
      '<div class="cr-end" role="document">' +
      "<h2>THE END</h2>" +
      "<p>NICO GOT THE BALL. GOOD BOY.</p>" +
      '<div class="row">' +
      '<button type="button" class="btn btn-warning" data-cr="replay">↺ REPLAY</button>' +
      '<button type="button" class="btn btn-primary" data-cr="close">BACK TO THE BOARD</button>' +
      "</div></div>";
    mountAll(root);
  }

  function clearTimers() {
    timers.forEach(clearTimeout);
    timers = [];
  }

  function applyStep(root, step) {
    if (step.charAt(0) === "-") root.classList.remove(step.slice(1));
    else root.classList.add(step);
  }

  function skipToEnd(root) {
    clearTimers();
    root.classList.add("is-skipped", "is-arriving", "is-parked", "is-caught", "is-ended");
    root.classList.remove("is-jumping", "is-throwing");
    const btn = $("[data-cr=close]", root);
    if (btn) btn.focus();
  }

  function openCredits() {
    const root = document.getElementById("credits");
    if (!root) return;
    clearTimers();
    lastFocus = document.activeElement;
    root.className = "credits";
    buildCredits(root);
    root.hidden = false;
    document.body.style.overflow = "hidden";
    const skip = $("[data-cr=skip]", root);
    if (skip) skip.focus();
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      skipToEnd(root);
      return;
    }
    TIMELINE.forEach(([t, step]) => {
      timers.push(setTimeout(() => applyStep(root, step), t));
    });
    timers.push(setTimeout(() => {
      const btn = $("[data-cr=close]", root);
      if (btn) btn.focus();
    }, 26600));
  }

  function closeCredits() {
    const root = document.getElementById("credits");
    if (!root || root.hidden) return;
    clearTimers();
    root.hidden = true;
    root.innerHTML = "";
    document.body.style.overflow = "";
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  function wireCredits() {
    document.addEventListener("click", (e) => {
      const opener = e.target.closest("[data-credits]");
      if (opener) {
        const panel = document.getElementById("intro-options-panel");
        if (panel) panel.hidden = true;
        openCredits();
        return;
      }
      const act = e.target.closest("[data-cr]");
      if (!act) return;
      const root = document.getElementById("credits");
      if (act.dataset.cr === "skip") skipToEnd(root);
      if (act.dataset.cr === "replay") openCredits();
      if (act.dataset.cr === "close") closeCredits();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeCredits();
    });
  }

  function init() {
    mountAll();
    const watch = ["app-shell", "rundown-view", "edition-view"]
      .map((id) => document.getElementById(id))
      .filter(Boolean);
    const mo = new MutationObserver(syncAppScene);
    watch.forEach((el) => mo.observe(el, { attributes: true, attributeFilter: ["hidden"] }));
    syncAppScene();
    wireCredits();
  }

  document.addEventListener("DOMContentLoaded", init);
  window.SSArcade = { openCredits, closeCredits };
})();
