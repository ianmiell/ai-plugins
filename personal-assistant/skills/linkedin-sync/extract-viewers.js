// extract-viewers.js: run on https://www.linkedin.com/analytics/profile-views/ (sorted by Most
// recent, the default) with Claude in Chrome's javascript_tool, after replacing __SINCE__ with the
// last sync time as an ISO date-time such as 2026-10-13T08:30:00Z (see SKILL.md step 4).
//
// First checks for Premium: without it LinkedIn shows only a few viewers behind an upsell, so it
// returns {premium: false, reason} and reads nothing. With it, scrolls the list (it lives in <main>,
// not the window) at a human pace until it reaches viewers from before SINCE. Returns JSON:
//   {premium: true, done, loaded, count, firstDegree, undated}  or  {premium: false, reason}  or  {error}
// done is false if it stopped after MAX_SCROLLS this call: run it again and it carries on. When
// done, it replaces the page's <main> with the viewers since SINCE who are not 1st-degree
// connections, newest first, one JSON object {url, name, headline, degree, viewed} per line between
// VIEWERS-BEGIN and VIEWERS-END <count> lines, to be read with get_page_text. Anonymous viewers
// ("Someone at ...") have no profile link and are left out.
// The page only gives relative times ("Viewed 3h ago", "Viewed 2w ago"), so a viewer counts as
// since SINCE if the view could have been after it: "2w ago" means between 2 and 3 weeks ago.
// Class names on the page are generated, so it goes by structure: /in/ profile links whose text
// holds "Viewed ".
await (async () => {
  const SINCE = new Date("__SINCE__");
  const MAX_SCROLLS = 15;  // per call, ~7 viewers each
  const MAX_CARDS = 300;
  const UNITS = {m: 60e3, h: 3600e3, d: 86400e3, w: 7 * 86400e3, mo: 30 * 86400e3, y: 365 * 86400e3};
  const UPSELL = /Try Premium|Reactivate Premium|Get Premium|Unlock (all|the full list|who)|with Premium|Premium free|free trial/i;
  const main = document.querySelector("main");
  if (!/\/analytics\/profile-views/.test(location.pathname) || !main) {
    return JSON.stringify({error: `not on the profile views page (${location.href}): signed out, or a security check?`});
  }
  if (isNaN(SINCE)) return JSON.stringify({error: "__SINCE__ was not replaced with an ISO date-time"});
  const upsell = (document.body.innerText.match(UPSELL) || [])[0];
  if (upsell) return JSON.stringify({premium: false, reason: `the page shows "${upsell}"`});

  const now = Date.now();
  // The latest time the view could have been, or null if the page's wording isn't understood
  const latest = text => {
    if (/Viewed just now/i.test(text)) return now;
    const m = text.match(/Viewed (\d+)\s*(mo|m|h|d|w|y)\b/);
    return m ? now - Number(m[1]) * UNITS[m[2]] : null;
  };
  const cards = () => {
    const found = new Map();
    for (const a of main.querySelectorAll('a[href*="/in/"]')) {
      const m = a.href.match(/^https:\/\/www\.linkedin\.com\/in\/([^/?#]+)/);
      const text = a.innerText || "";
      if (!m || !/Viewed /.test(text) || found.has(m[1])) continue;
      const lines = text.split("\n").map(s => s.trim()).filter(Boolean);
      const degree = (text.match(/•\s*(1st|2nd|3rd\+?)/) || [])[1] || "";
      found.set(m[1], {
        url: `https://www.linkedin.com/in/${m[1]}`,
        name: lines[0] || "",
        headline: lines.filter(s => !/^•|^Viewed /.test(s)).slice(1).join(" "),
        degree,
        viewed: (text.match(/Viewed [^\n]*/) || [])[0],
        at: latest(text),
      });
    }
    return [...found.values()];
  };
  const finished = list => list.some(c => c.at !== null && c.at < SINCE) || list.length >= MAX_CARDS;
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  let list = cards(), done = finished(list), stuck = 0;
  if (!list.length) return JSON.stringify({error: "no viewers with profile links on the page: has the layout changed?"});
  for (let i = 0; i < MAX_SCROLLS && !done; i++) {
    const before = list.length;
    main.scrollTo(0, main.scrollHeight);
    await sleep(2500 + Math.random() * 2000);
    list = cards();
    // No new cards three times running: the end of the list
    stuck = list.length === before ? stuck + 1 : 0;
    done = finished(list) || stuck >= 3;
  }
  const recent = list.filter(c => c.at !== null && c.at >= SINCE);
  const wanted = recent.filter(c => c.name && c.degree !== "1st");
  if (done) {
    const pre = document.createElement("pre");
    pre.textContent = ["VIEWERS-BEGIN",
      ...wanted.map(({url, name, headline, degree, viewed}) => JSON.stringify({url, name, headline, degree, viewed})),
      `VIEWERS-END ${wanted.length}`].join("\n");
    main.replaceChildren(pre);
  }
  return JSON.stringify({premium: true, done, loaded: list.length, count: wanted.length,
    firstDegree: recent.length - wanted.length, undated: list.filter(c => c.at === null).length});
})()
