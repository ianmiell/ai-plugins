// toggl-fill.js: run on the Toggl Track Timesheet view with Claude in Chrome's javascript_tool,
// after toggl-grid.js has been run on the same page (it leaves the cell finder behind), and after
// replacing __PLAN__ with the plan from `timesheet.py propose` (the line after "plan:"), e.g.
//   {"CCF": {"Mon": "8:00", "Tue": "8:00", "Wed": ""}, "Pre sales work": {"Wed": "8:00"}}
// "" clears a cell. Days not in the plan are left alone.
//
// Sets only the cells whose value differs, one at a time: focus, the native value setter (so the
// page's own code sees the change), input and change events, then blur, which is when Toggl saves.
// It waits a moment after each, and finds the cells again each time in case the page redraws.
// Returns JSON {set: [{project, day, from, to}], unchanged, missingRows, failed, note} or {error}.
// Then read the grid again with toggl-grid.js and run `timesheet.py check`: this only says what
// it typed, not what Toggl kept. A missing row needs "+ Add row" by hand (SKILL.md step 5), and a
// failed cell the click-and-type method.
await (async () => {
  const PLAN = __PLAN__;
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const minutes = v => {
    const s = String(v || "").trim().replace(/h$/i, "").trim();
    if (!s || s === "-") return 0;
    const m = s.match(/^(\d+):(\d{2})(?::\d{2})?$/);
    if (m) return Number(m[1]) * 60 + Number(m[2]);
    return /^\d+(\.\d+)?$/.test(s) ? Math.round(Number(s) * 60) : NaN;
  };
  const norm = s => String(s || "").toLowerCase().replace(/\s+/g, " ").trim();
  if (typeof PLAN !== "object" || !PLAN) return JSON.stringify({error: "__PLAN__ was not replaced with the plan JSON"});
  if (!window.__togglGrid) return JSON.stringify({error: "run toggl-grid.js on this page first (it defines the cell finder)"});
  const find = () => {
    const g = window.__togglGrid.locate();
    if (g.error) return g;
    if (!g.editable) return {error: `the week isn't editable (status ${g.status || "unknown"}): nothing changed`};
    return g;
  };
  const rowFor = (g, project) => {
    const p = norm(project);
    return g.rows.find(r => !r.total && norm(r.project) === p) || g.rows.find(r => !r.total && norm(r.project).startsWith(p));
  };
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  const set = [], unchanged = [], missingRows = [], failed = [];
  let g = find();
  if (g.error) return JSON.stringify(g);
  for (const [project, days] of Object.entries(PLAN)) {
    if (!rowFor(g, project)) { missingRows.push(project); continue; }
    for (const [day, want] of Object.entries(days || {})) {
      if (!DAYS.includes(day)) { failed.push({project, day, why: "not a day name (Mon..Sun)"}); continue; }
      g = find();
      if (g.error) return JSON.stringify({...g, set, unchanged, missingRows, failed});
      const el = rowFor(g, project)?.inputs[day];
      if (!el || el.tagName !== "INPUT") { failed.push({project, day, why: "no input in that cell"}); continue; }
      const from = el.value;
      if (minutes(from) === minutes(want)) { unchanged.push(`${project} ${day}`); continue; }
      el.scrollIntoView({block: "center"});
      el.focus();
      el.dispatchEvent(new FocusEvent("focusin", {bubbles: true}));
      await sleep(150);
      setter.call(el, String(want));
      el.dispatchEvent(new InputEvent("input", {bubbles: true, inputType: "insertText", data: String(want)}));
      el.dispatchEvent(new Event("change", {bubbles: true}));
      el.blur();
      el.dispatchEvent(new FocusEvent("focusout", {bubbles: true}));
      await sleep(600);
      set.push({project, day, from, to: String(want)});
    }
  }
  return JSON.stringify({set, unchanged: unchanged.length, missingRows, failed,
    note: "now read the grid again with toggl-grid.js and run timesheet.py check"});
})();
