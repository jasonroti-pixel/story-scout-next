/**
 * Story Scout Next — clip link-out helpers (metadata only, no media in repo).
 */
(function (global) {
  "use strict";

  function platformLabel(platform) {
    const p = String(platform || "web").toLowerCase();
    const map = {
      youtube: "YouTube",
      tiktok: "TikTok",
      instagram: "Instagram",
      twitter: "X / Twitter",
      x: "X / Twitter",
      vimeo: "Vimeo",
      web: "Web",
    };
    return map[p] || platform || "Link";
  }

  function formatDuration(seconds) {
    if (seconds == null || seconds === "" || Number.isNaN(Number(seconds))) return "";
    const s = Math.max(0, Math.floor(Number(seconds)));
    const m = Math.floor(s / 60);
    const r = s % 60;
    return m + ":" + String(r).padStart(2, "0");
  }

  function renderClipList(clips) {
    if (!clips || !clips.length) {
      return '<p class="nes-text is-disabled">No clips linked.</p>';
    }
    const items = clips
      .map((c) => {
        const thumb = c.thumbnail_url
          ? `<img src="${escapeAttr(c.thumbnail_url)}" alt="" loading="lazy" referrerpolicy="no-referrer" />`
          : "";
        const dur = formatDuration(c.duration_seconds);
        const desc = escapeHtml(c.description || platformLabel(c.platform));
        const url = escapeAttr(c.url || "#");
        return `<li>
          ${thumb}
          <div>
            <div><strong>${escapeHtml(platformLabel(c.platform))}</strong>
              ${c.type ? " · " + escapeHtml(c.type) : ""}
              ${dur ? " · " + dur : ""}</div>
            <div>${desc}</div>
            <a href="${url}" target="_blank" rel="noopener noreferrer">Open clip ↗</a>
          </div>
        </li>`;
      })
      .join("");
    return `<ul class="clip-list">${items}</ul>`;
  }

  function clipCountBadge(clips) {
    const n = (clips && clips.length) || 0;
    if (!n) return "";
    return `<span class="clip-badge" title="Linked clips">${n} clip${n === 1 ? "" : "s"}</span>`;
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(str) {
    return escapeHtml(str).replace(/'/g, "&#39;");
  }

  global.SSClips = {
    platformLabel,
    formatDuration,
    renderClipList,
    clipCountBadge,
    escapeHtml,
    escapeAttr,
  };
})(window);
