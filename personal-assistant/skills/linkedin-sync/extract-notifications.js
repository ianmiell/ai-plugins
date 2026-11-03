// extract-notifications.js: run on https://www.linkedin.com/notifications/ (the All tab, the
// default) with Claude in Chrome's javascript_tool, after replacing __SINCE__ with the last sync
// time as an ISO date-time such as 2026-10-13T08:30:00Z (see SKILL.md step 5c).
//
// Scrolls the list at a human pace until it reaches notifications from before SINCE, and reads
// every notification that names a person (an /in/ profile link): comments on Ian's posts, replies,
// mentions, reactions, reposts, their own posts, new jobs and work anniversaries. Returns JSON:
//   {done, loaded, count}  or  {error}
// done is false if it stopped after MAX_SCROLLS this call: run it again and it carries on. When
// done, it replaces the page's <main> with the notifications since SINCE, newest first, one JSON
// object {urls, text, age} per line between NOTIFICATIONS-BEGIN and NOTIFICATIONS-END <count>
// lines, to be read with get_page_text. `urls` are the profile links in the notification (the
// people it names first), `text` its words (up to 400 characters), `age` as the page shows it
// ("21m", "3h", "2d"). Notifications naming nobody ("Your post got 600 impressions") are left out.
// The page only gives relative times, so a notification counts as since SINCE if it could have been
// after it: "2d" means between 2 and 3 days ago.
// Its only click is "Show more results" at the foot of the list, when the page has one. It never
// opens a notification (that marks it read) or clicks anything in one.
// Class names on the page are generated, so it goes by structure: the /in/ links, and the card
// around each one whose text ends with its age (Ian's own card in the sidebar has none).
await (async () => {
  const SINCE = new Date("__SINCE__");
  const MAX_SCROLLS = 8;   // per call: javascript_tool gives up after 45s
  const MAX_CARDS = 150;
  const UNITS = {m: 60e3, h: 3600e3, d: 86400e3, w: 7 * 86400e3, mo: 30 * 86400e3, y: 365 * 86400e3};
  const AGE = /\n\s*(\d+)\s*(mo|m|h|d|w|y)\s*$/;
  const main = document.querySelector("main");
  if (!/^\/notifications/.test(location.pathname) || !main) {
    return JSON.stringify({error: `not on the notifications page (${location.href}): signed out, or a security check?`});
  }
  if (isNaN(SINCE)) return JSON.stringify({error: "__SINCE__ was not replaced with an ISO date-time"});
  if (main.innerText.startsWith("NOTIFICATIONS-BEGIN")) {
    return JSON.stringify({error: "the list is already written: read it with get_page_text"});
  }
  const now = Date.now();
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const slugOf = href => (href.match(/^https:\/\/www\.linkedin\.com\/in\/([^/?#]+)/) || [])[1];

  const cards = () => {
    const found = new Map();
    for (const a of main.querySelectorAll('a[href*="/in/"]')) {
      const slug = slugOf(a.href);
      if (!slug) continue;
      let card = a;
      while (card && card !== main && !AGE.test((card.innerText || "").trim())) card = card.parentElement;
      if (!card || card === main) continue;
      const text = (card.innerText || "").trim();
      const m = text.match(AGE);
      if (!m) continue;
      const rec = found.get(card) || {urls: [], text: text.slice(0, -m[0].length).replace(/\s+/g, " ").trim().slice(0, 400),
        age: `${m[1]}${m[2]}`, at: now - Number(m[1]) * UNITS[m[2]]};
      const url = `https://www.linkedin.com/in/${slug}`;
      if (!rec.urls.includes(url)) rec.urls.push(url);
      found.set(card, rec);
    }
    return [...found.values()];
  };
  const finished = list => list.some(c => c.at < SINCE) || list.length >= MAX_CARDS;

  let list = cards(), done = finished(list), stuck = 0;
  for (let i = 0; i < MAX_SCROLLS && !done; i++) {
    const before = list.length;
    window.scrollTo(0, document.documentElement.scrollHeight);
    main.scrollTo && main.scrollTo(0, main.scrollHeight);
    await sleep(2500 + Math.random() * 2000);
    const more = [...main.querySelectorAll("button")].find(b => /^Show more results$/.test((b.innerText || "").trim()) && b.offsetParent !== null);
    if (more) {
      more.click();
      await sleep(2000 + Math.random() * 1000);
    }
    list = cards();
    // No new cards three times running: the end of the list
    stuck = list.length === before ? stuck + 1 : 0;
    done = finished(list) || stuck >= 3;
  }
  const recent = list.filter(c => c.at >= SINCE);
  if (done) {
    const pre = document.createElement("pre");
    pre.textContent = ["NOTIFICATIONS-BEGIN",
      ...recent.map(({urls, text, age}) => JSON.stringify({urls, text, age})),
      `NOTIFICATIONS-END ${recent.length}`].join("\n");
    main.replaceChildren(pre);
  }
  return JSON.stringify({done, loaded: list.length, count: recent.length});
})()
