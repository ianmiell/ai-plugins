// extract-connections.js: run on https://www.linkedin.com/mynetwork/invite-connect/connections/
// (sorted by Recently added, the default) with Claude in Chrome's javascript_tool, after replacing
// __SINCE__ with a YYYY-MM-DD date (see SKILL.md step 2).
//
// Scrolls the list (it lives in <main>, not the window) a few cards at a time, at a human pace,
// until it has loaded every card connected on or after SINCE. Returns JSON:
//   {done, loaded, capped, count}  or  {error}
// done is false if it stopped after MAX_SCROLLS this call: run it again and it carries on from the
// cards already loaded. When done, it replaces the page's <main> with the cards connected on or after
// SINCE, newest first, one JSON object {url, name, headline, connected} per line between
// GTD-SYNC-BEGIN and GTD-SYNC-END <count> lines, to be read with get_page_text (javascript_tool
// truncates long results). `connected` is as the page shows it ("October 16, 2026"), and `url` is the
// profile link as LinkedIn wrote it.
// Class names on the page are generated, so it goes by structure: /in/ profile links, and the
// "Connected on" text in the card around them.
await (async () => {
  const SINCE = new Date("__SINCE__T00:00:00");
  const MAX_SCROLLS = 8;   // per call, ~10 cards each: javascript_tool gives up after 45s
  const MAX_CARDS = 400;   // past this, leave the rest to the monthly data export
  const main = document.querySelector("main");
  if (!/\/mynetwork\/invite-connect\/connections/.test(location.pathname) || !main) {
    return JSON.stringify({error: `not on the connections page (${location.href}): signed out, or a security check?`});
  }
  if (isNaN(SINCE)) return JSON.stringify({error: "__SINCE__ was not replaced with a YYYY-MM-DD date"});

  const cards = () => {
    const found = new Map();
    for (const a of main.querySelectorAll('a[href*="/in/"]')) {
      const m = a.href.match(/^https:\/\/www\.linkedin\.com\/in\/([^/?#]+)/);
      if (!m) continue;
      let card = a;
      while (card && card !== main && !/Connected on /.test(card.innerText || "")) card = card.parentElement;
      if (!card || card === main) continue;
      const rec = found.get(m[1]) || {url: `https://www.linkedin.com/in/${m[1]}`, name: "", headline: "",
        connected: (card.innerText.match(/Connected on ([A-Z][a-z]+ \d{1,2}, \d{4})/) || [])[1] || ""};
      const lines = (a.innerText || "").split("\n").map(s => s.trim()).filter(Boolean);
      if (lines.length && !rec.name) {
        rec.name = lines[0];
        rec.headline = lines.slice(1).join(" ");
      }
      found.set(m[1], rec);
    }
    return [...found.values()];
  };
  const oldest = list => list.reduce((min, c) => {
    const d = new Date(c.connected);
    return isNaN(d) ? min : (min === null || d < min ? d : min);
  }, null);
  const finished = list => (oldest(list) !== null && oldest(list) < SINCE) || list.length >= MAX_CARDS;
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  let list = cards(), done = finished(list), stuck = 0;
  for (let i = 0; i < MAX_SCROLLS && !done; i++) {
    const before = list.length;
    main.scrollTo(0, main.scrollHeight);
    await sleep(2500 + Math.random() * 2000);
    list = cards();
    // No new cards three times running: the end of the list
    stuck = list.length === before ? stuck + 1 : 0;
    done = finished(list) || stuck >= 3;
  }
  const recent = list.filter(c => c.name && !(new Date(c.connected) < SINCE));
  if (done) {
    const pre = document.createElement("pre");
    pre.textContent = ["GTD-SYNC-BEGIN", ...recent.map(c => JSON.stringify(c)), `GTD-SYNC-END ${recent.length}`].join("\n");
    main.replaceChildren(pre);
  }
  return JSON.stringify({done, loaded: list.length, capped: list.length >= MAX_CARDS, count: recent.length});
})()
