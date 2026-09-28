/* Story Scout Next v2 — Loadout ("prep") — production behavior clone.
 *
 * Mirrors the original Story Scout Arcade loadout exactly:
 *  - selection = Set of composite story IDs: date|slot|title[0:60]
 *  - clicking a story card toggles it in/out of the loadout
 *  - auto-saved to this browser's localStorage after every change
 *  - panel: LOADOUT - PREP SHEET, SELECT ALL / COPY / PRINT / EMAIL / CLEAR,
 *    date-grouped items with X remove, arcade empty state
 *  - exports built from one buildPrepText() format
 * Skin is Peak Arcade; behavior is the original.
 */
(function (global) {
  "use strict";

  var LS_KEY = "jaystation-sel-v2"; // per-browser: each producer's own loadout
  var OLD_KEY = "ssn-v2-loadout-v1"; // pre-clone format, migrated once
  var MIG_KEY = "jaystation-sel-v2-migrated";

  var selectedIds = new Set();
  var stories = []; // ordered story array (board order), set via setStories
  var byId = new Map();

  function storyId(s) {
    return (
      String(s.date || "") +
      "|" +
      String(s.slot || "") +
      "|" +
      String(s.title || "").substring(0, 60)
    );
  }

  function escHtml(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }
  function escAttr(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;")
      .replace(/</g, "&lt;");
  }
  function toast(msg) {
    if (typeof global.showToast === "function") global.showToast(msg);
  }

  function saveSelections() {
    try {
      global.localStorage.setItem(LS_KEY, JSON.stringify(Array.from(selectedIds)));
    } catch (e) {}
  }

  function setStories(list) {
    stories = Array.isArray(list) ? list : [];
    byId = new Map();
    stories.forEach(function (s) {
      byId.set(storyId(s), s);
    });
  }

  function getSelectedStories() {
    var out = [];
    stories.forEach(function (s) {
      if (selectedIds.has(storyId(s))) out.push(s);
    });
    return out;
  }

  function toggleStory(id) {
    id = String(id);
    var res;
    if (selectedIds.has(id)) {
      selectedIds.delete(id);
      toast("REMOVED FROM LOADOUT");
      res = "removed";
    } else {
      selectedIds.add(id);
      toast("ADDED TO LOADOUT");
      res = "added";
    }
    saveSelections();
    render();
    return res;
  }

  function has(id) {
    return selectedIds.has(String(id));
  }

  function removeFromPrep(id, silent) {
    selectedIds.delete(String(id));
    saveSelections();
    render();
    if (!silent) toast("REMOVED FROM LOADOUT");
  }

  function clearPrep() {
    selectedIds.clear();
    saveSelections();
    render();
    toast("LOADOUT CLEARED");
  }

  function selectAllVisible(list) {
    var n = 0;
    (list || []).forEach(function (s) {
      var id = storyId(s);
      if (!selectedIds.has(id)) {
        selectedIds.add(id);
        n++;
      }
    });
    saveSelections();
    render();
    toast(n + " STORIES ADDED");
    return n;
  }

  function slotLabel(s) {
    return s === "am" ? "MORNING" : s === "pm" ? "EVENING" : "FULL REPORT";
  }
  function formatFull(ds) {
    var parts = String(ds || "").split("-");
    var dt = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    return dt.toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  }

  function updateCount() {
    var n = selectedIds.size;
    var badge = document.getElementById("loadout-count");
    if (badge) badge.textContent = String(n);
    var c = document.getElementById("prepCount");
    if (c) c.textContent = String(n);
  }

  function render() {
    updateCount();
    var list = document.getElementById("prepList");
    var actions = document.getElementById("prepActions");
    if (!list) return;
    var sel = getSelectedStories();
    if (actions) actions.style.display = sel.length ? "flex" : "none";
    if (!sel.length) {
      list.innerHTML =
        '<div class="prep-empty">SELECT STORIES FROM<br>THE BROWSER TO BUILD<br>YOUR LOADOUT<br><br><span class="blink">WAITING FOR INPUT_</span></div>';
      return;
    }
    var byDate = {};
    sel.forEach(function (s) {
      var k = (s.date || "") + " " + (s.slot || "");
      if (!byDate[k]) byDate[k] = [];
      byDate[k].push(s);
    });
    var h = "";
    Object.keys(byDate)
      .sort()
      .reverse()
      .forEach(function (key) {
        var sp = key.split(" ");
        var date = sp[0],
          slot = sp[1];
        h +=
          '<div class="prep-date-group">' +
          escHtml(formatFull(date).toUpperCase()) +
          " - " +
          escHtml(slotLabel(slot)) +
          "</div>";
        byDate[key].forEach(function (s) {
          var id = escAttr(storyId(s));
          h +=
            '<div class="prep-item" data-prep-id="' +
            id +
            '"><button class="prep-remove" title="Remove">X</button>';
          h +=
            '<div class="prep-item-cat">' +
            (s._custom ? '<span class="prep-custom-tag">CUSTOM</span>' : "") +
            escHtml(s.category || "") +
            "</div>";
          h += '<div class="prep-item-title">' + escHtml(s.title || "") + "</div>";
          if (s.angle)
            h += '<div class="prep-item-angle">' + escHtml(s.angle) + "</div>";
          if (s.debate)
            h += '<div class="prep-item-debate">' + escHtml(s.debate) + "</div>";
          if (s.url)
            h +=
              '<a class="prep-item-url" href="' +
              escAttr(s.url) +
              '" target="_blank" rel="noopener">' +
              escHtml(s.url) +
              "</a>";
          h += "</div>";
        });
      });
    list.innerHTML = h;
  }

  function buildPrepText() {
    var sel = getSelectedStories();
    if (!sel.length) return "";
    var bar = "════════════════════════════════════════\n";
    var t = bar;
    t += "  THE DAILY GOODS - RADIO SHOW PREP SHEET\n";
    t += "  Story Scout Next\n";
    t += bar;
    t +=
      "Generated: " +
      new Date().toLocaleDateString("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }) +
      "\n";
    t += "Stories selected: " + sel.length + "\n";
    t += bar + "\n";
    var byDate = {};
    sel.forEach(function (s) {
      var k = (s.date || "") + " " + (s.slot || "");
      if (!byDate[k]) byDate[k] = [];
      byDate[k].push(s);
    });
    Object.keys(byDate)
      .sort()
      .reverse()
      .forEach(function (key) {
        var sp = key.split(" ");
        var date = sp[0],
          slot = sp[1];
        t +=
          "--- " + formatFull(date).toUpperCase() + " (" + slotLabel(slot) + ") ---\n\n";
        byDate[key].forEach(function (s, i) {
          t += i + 1 + ". " + (s._custom ? "[CUSTOM] " : "") + (s.title || "") + "\n";
          t += "   Category: " + (s.category || "") + "\n";
          if (s.angle) t += "   Angle: " + s.angle + "\n";
          if (s.bullets && s.bullets.length)
            s.bullets.forEach(function (b) {
              t += "   - " + String(b).trim() + "\n";
            });
          if (s.debate) t += "   Debate Starter: " + s.debate + "\n";
          if (s.url) t += "   Source: " + s.url + "\n";
          t += "\n";
        });
      });
    return t;
  }

  function copyPrep() {
    var t = buildPrepText();
    if (!t) {
      toast("LOADOUT IS EMPTY");
      return Promise.resolve(false);
    }
    function done() {
      toast("COPIED TO CLIPBOARD");
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard
        .writeText(t)
        .then(function () {
          done();
          return true;
        })
        .catch(function () {
          fallbackCopy(t);
          done();
          return true;
        });
    }
    fallbackCopy(t);
    done();
    return Promise.resolve(true);
  }
  function fallbackCopy(t) {
    try {
      var ta = document.createElement("textarea");
      ta.value = t;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    } catch (e) {}
  }
  function selectAllText() {
    copyPrep();
  }
  function printPrep() {
    global.print();
  }
  function emailPrep() {
    var t = buildPrepText();
    if (!t) {
      toast("LOADOUT IS EMPTY");
      return;
    }
    var subj = encodeURIComponent(
      "THE DAILY GOODS Prep Sheet - " + new Date().toLocaleDateString()
    );
    var body = encodeURIComponent(t);
    global.open("mailto:?subject=" + subj + "&body=" + body);
    toast("EMAIL CLIENT OPENED");
  }

  function restore() {
    var raw = null;
    try {
      raw = global.localStorage.getItem(LS_KEY);
    } catch (e) {}
    if (raw) {
      try {
        selectedIds = new Set(JSON.parse(raw));
      } catch (e) {}
    }
    // One-time migration from the pre-clone format (story ids -> composite ids).
    try {
      if (
        !global.localStorage.getItem(MIG_KEY) &&
        stories.length &&
        !selectedIds.size
      ) {
        var old = global.localStorage.getItem(OLD_KEY);
        if (old) {
          var ids = JSON.parse(old);
          var idx = new Map();
          stories.forEach(function (s) {
            idx.set(String(s.id), s);
          });
          (Array.isArray(ids) ? ids : []).forEach(function (entry) {
            var sid =
              entry && entry.id != null ? String(entry.id) : String(entry);
            var s = idx.get(sid);
            if (s) selectedIds.add(storyId(s));
          });
          if (selectedIds.size) saveSelections();
          global.localStorage.removeItem(OLD_KEY);
        }
        global.localStorage.setItem(MIG_KEY, "1");
      }
    } catch (e) {}
    // Drop selections that no longer match any known story.
    var kept = new Set();
    selectedIds.forEach(function (id) {
      if (byId.has(id)) kept.add(id);
    });
    if (kept.size !== selectedIds.size) {
      selectedIds = kept;
      saveSelections();
    }
    render();
  }

  // Remove-button delegation inside the panel.
  document.addEventListener("click", function (e) {
    var rm = e.target.closest ? e.target.closest(".prep-remove") : null;
    if (!rm) return;
    var item = rm.closest(".prep-item");
    if (item && item.getAttribute("data-prep-id")) {
      removeFromPrep(item.getAttribute("data-prep-id"));
      if (typeof global.SSLoadoutCardsChanged === "function") {
        try {
          global.SSLoadoutCardsChanged();
        } catch (err) {}
      }
    }
  });

  global.SSLoadout = {
    storyId: storyId,
    setStories: setStories,
    getSelectedStories: getSelectedStories,
    toggleStory: toggleStory,
    has: has,
    removeFromPrep: removeFromPrep,
    clearPrep: clearPrep,
    selectAllVisible: selectAllVisible,
    buildPrepText: buildPrepText,
    copyPrep: copyPrep,
    selectAllText: selectAllText,
    printPrep: printPrep,
    emailPrep: emailPrep,
    restore: restore,
    render: render,
    updateCount: updateCount,
    count: function () {
      return selectedIds.size;
    },
  };
})(window);
