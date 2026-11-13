// toggl-grid.js: run on https://track.toggl.com/timer, Timesheet view, with Claude in Chrome's
// javascript_tool, as is (nothing to replace). Reads the week's timesheet grid and returns JSON:
//   {week, weekNumber, dateRange, status, buttons, editable, dates: {Mon: "26", ...},
//    rows: [{project, client, label, cells: {Mon: "8:00", ..., Sun: ""}, total}],
//    totals: {Mon: "8:00", ..., week: "40:00"}, warnings: [...]}
// or {error: "..."} saying what it couldn't find, so the page can be checked by eye instead.
// timesheet.py reads this JSON (propose, check, submitted).
//
// It also leaves window.__togglGrid.locate() on the page, which toggl-fill.js uses to find the
// same cells. It changes nothing on the page.
//
// Toggl's class names are generated, so it goes by what the page shows (SKILL.md, Setup): seven
// day headers MON..SUN in a row; rows labelled "PROJECT • CLIENT" to their left; a cell (an input
// when the week is editable, plain text when it is locked) under each day; a TOTAL column on the
// right and a TOTAL row below; a status chip (NOT SUBMITTED, BEING REVIEWED, APPROVED).
await (async () => {
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const DAY_RE = /^(mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s*(\d{1,2})?\b/i;
  const DUR_RE = /^(\d{1,3}(:\d{2}){0,2}|\d+(\.\d+)?)\s*h?$/i;
  const STATUS_RE = /^(not submitted|being reviewed|approved|rejected|submitted|pending( approval)?|changes requested)$/i;
  const SKIP_RE = /^(project|projects|\+?\s*add row|copy last week|add description|select project)$/i;
  const LOCKED = /being reviewed|approved|submitted/i;

  const textNodes = root => {
    const out = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: n => n.nodeValue.trim() && !/^(SCRIPT|STYLE|NOSCRIPT)$/.test(n.parentElement?.tagName || "")
        ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT,
    });
    const range = document.createRange();
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      range.selectNodeContents(n);
      const r = range.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) out.push({text: n.nodeValue.trim(), el: n.parentElement, r});
    }
    return out;
  };
  const mid = r => ({x: (r.left + r.right) / 2, y: (r.top + r.bottom) / 2});

  const locate = () => {
    if (!/track\.toggl\.com/.test(location.host)) return {error: `not on Toggl Track (${location.href})`};
    const all = textNodes(document.body);
    // The day headers: seven nodes on one line, Mon to Sun left to right.
    const byTop = new Map();
    for (const t of all) {
      const m = t.text.match(DAY_RE);
      if (!m || t.text.length > 16) continue;
      const k = Math.round(t.r.top / 6);
      if (!byTop.has(k)) byTop.set(k, []);
      byTop.get(k).push({...t, day: m[1].slice(0, 1).toUpperCase() + m[1].slice(1, 3).toLowerCase(), date: m[2] || ""});
    }
    let headers = null;
    for (const list of byTop.values()) {
      const seen = new Map();
      for (const h of list.sort((a, b) => a.r.left - b.r.left)) if (!seen.has(h.day)) seen.set(h.day, h);
      const order = [...seen.values()].map(h => h.day);
      if (DAYS.every((d, i) => order[i] === d)) { headers = [...seen.values()]; break; }
    }
    if (!headers) {
      return {error: "no row of day headers MON..SUN found: is the Timesheet view selected (not Calendar or List view)?"};
    }
    const cols = headers.map(h => ({day: h.day, date: h.date, x: mid(h.r).x}));
    const pitch = (cols[6].x - cols[0].x) / 6;
    const headBottom = Math.max(...headers.map(h => h.r.bottom));
    const gridLeft = cols[0].x - pitch / 2;
    const gridRight = cols[6].x + pitch / 2;
    const colOf = x => {
      const i = Math.round((x - cols[0].x) / pitch);
      return i >= 0 && i < 7 && Math.abs(x - cols[i].x) < pitch / 2 ? cols[i].day : (x >= gridRight ? "TOTAL" : null);
    };
    // Dates under the headers, when they are separate nodes ("MON" then "26").
    for (const t of all) {
      if (/^\d{1,2}$/.test(t.text) && t.r.top >= headers[0].r.top - 20 && t.r.bottom <= headBottom + 24) {
        const c = colOf(mid(t.r).x);
        const col = cols.find(k => k.day === c);
        if (col && !col.date) col.date = t.text;
      }
    }
    // The area the grid can be in: from the headers' container down, not the side navigation.
    let box = headers[0].el;
    while (box && box !== document.body && !headers.every(h => box.contains(h.el))) box = box.parentElement;
    for (let i = 0; i < 8 && box && box !== document.body; i++) {
      if (/add row|copy last week|^total$/im.test(box.innerText) && box.getBoundingClientRect().bottom > headBottom + 30) break;
      box = box.parentElement;
    }
    const boxRect = (box || document.body).getBoundingClientRect();
    // Row labels: text left of the Monday column, below the headers, grouped into lines.
    const labels = all.filter(t => t.r.top >= headBottom - 2 && t.r.right <= gridLeft + 4 && t.r.left >= boxRect.left - 1 &&
      (box || document.body).contains(t.el) && !SKIP_RE.test(t.text)).sort((a, b) => a.r.top - b.r.top || a.r.left - b.r.left);
    const bands = [];
    for (const t of labels) {
      const b = bands[bands.length - 1];
      if (b && t.r.top <= b.bottom + 8) {
        b.parts.push(t.text);
        b.bottom = Math.max(b.bottom, t.r.bottom);
      } else {
        bands.push({parts: [t.text], top: t.r.top, bottom: t.r.bottom});
      }
    }
    for (const b of bands) b.y = (b.top + b.bottom) / 2;
    const half = i => {
      const prev = i > 0 ? bands[i].y - bands[i - 1].y : Infinity;
      const next = i < bands.length - 1 ? bands[i + 1].y - bands[i].y : Infinity;
      const p = Math.min(prev, next);
      return p === Infinity ? 30 : p / 2;
    };
    const bandOf = y => {
      let best = -1, dist = Infinity;
      bands.forEach((b, i) => {
        const d = Math.abs(y - b.y);
        if (d < dist && d <= half(i)) { best = i; dist = d; }
      });
      return best;
    };
    const inputs = [...document.querySelectorAll("input, textarea, [contenteditable='true']")].filter(el => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && r.left >= gridLeft - 4 && (box || document.body).contains(el);
    });
    const rows = bands.map(b => {
      const label = b.parts.join(" ").replace(/\s+/g, " ").trim();
      const [project, client] = label.split(/\s*•\s*/);
      return {label, project: (project || "").trim(), client: (client || "").trim(), total: /^total\b/i.test(label),
              inputs: {}, texts: {}, y: b.y};
    });
    for (const el of inputs) {
      const p = mid(el.getBoundingClientRect());
      const i = bandOf(p.y), c = colOf(p.x);
      if (i >= 0 && c && c !== "TOTAL" && !rows[i].inputs[c]) rows[i].inputs[c] = el;
    }
    for (const t of all) {
      if (!DUR_RE.test(t.text) || t.r.top < headBottom - 2) continue;
      const p = mid(t.r);
      const i = bandOf(p.y), c = colOf(p.x);
      if (i >= 0 && c && !rows[i].texts[c]) rows[i].texts[c] = t.text;
    }
    const status = (all.find(t => STATUS_RE.test(t.text)) || {}).text || "";
    const weekNode = all.find(t => /\bW\d{1,2}\b/.test(t.text) && t.text.length < 60);
    let week = weekNode ? weekNode.text : "";
    if (weekNode && weekNode.el.parentElement && weekNode.el.parentElement.innerText.length < 60) {
      week = weekNode.el.parentElement.innerText.replace(/\s+/g, " ").trim();
    }
    const rangeNode = all.find(t => /\d{1,2}\s+[A-Z][a-z]{2}\.?\s*[-–]\s*\d{1,2}\s+[A-Z][a-z]{2}/.test(t.text) && t.text.length < 60);
    const buttons = [...document.querySelectorAll("button, [role='button']")]
      .map(b => (b.innerText || b.getAttribute("aria-label") || "").replace(/\s+/g, " ").trim())
      .filter(s => /submit|withdraw|copy last week|add row|approv/i.test(s) && s.length < 40);
    const editable = inputs.some(el => !el.disabled && !el.readOnly) && !LOCKED.test(status);
    return {cols, rows, status, week, weekNumber: Number((week.match(/\bW(\d{1,2})\b/) || [])[1]) || null,
            dateRange: rangeNode ? rangeNode.text : "", buttons: [...new Set(buttons)], editable};
  };
  window.__togglGrid = {locate};

  const g = locate();
  if (g.error) return JSON.stringify(g);
  const value = (row, day) => {
    const el = row.inputs[day];
    const v = el ? (el.value !== undefined && el.tagName !== "DIV" ? el.value : el.innerText) : row.texts[day] || "";
    return String(v || "").trim();
  };
  const warnings = [];
  const rows = [], totals = {};
  for (const r of g.rows) {
    const cells = Object.fromEntries(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(d => [d, value(r, d)]));
    if (r.total) {
      Object.assign(totals, cells, {week: r.texts.TOTAL || ""});
      continue;
    }
    if (!Object.keys(r.inputs).length && !Object.keys(r.texts).length) {
      warnings.push(`no cells found for the row "${r.label}"`);
      continue;
    }
    rows.push({project: r.project, client: r.client, label: r.label, cells, total: r.texts.TOTAL || ""});
  }
  if (!rows.length) warnings.push("no project rows found: an empty week, or the layout has changed (check a screenshot)");
  if (!g.status) warnings.push("no status chip (NOT SUBMITTED / BEING REVIEWED / APPROVED) found");
  return JSON.stringify({week: g.week, weekNumber: g.weekNumber, dateRange: g.dateRange, status: g.status.toUpperCase(),
    buttons: g.buttons, editable: g.editable, dates: Object.fromEntries(g.cols.map(c => [c.day, c.date])),
    rows, totals, warnings});
})();
