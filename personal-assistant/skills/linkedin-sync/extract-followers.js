// extract-followers.js: run on https://www.linkedin.com/mynetwork/network-manager/people-follow/followers/
// with Claude in Chrome's javascript_tool (see SKILL.md step 5b). Nothing to replace.
//
// The list is newest first and loads 20 cards at a time as the window scrolls (or from "Show more
// results"). This scrolls at a human pace until MAX_CARDS followers are loaded or the list ends, and
// returns JSON:
//   {done, loaded, count}  or  {error}
// done is false if it stopped after MAX_SCROLLS this call: run it again and it carries on from the
// cards already loaded. When done, it puts the loaded followers Ian doesn't follow back (their button
// says Follow, not Following), newest first, at the top of <main>: one JSON object {url, name, headline}
// per line between FOLLOWERS-BEGIN and FOLLOWERS-END <count> lines, to be read with get_page_text
// (javascript_tool truncates long results). It keeps the cards, since follow-follower.js clicks
// Follow in them, and clicks nothing but "Show more results".
// Class names on the page are generated, so it goes by structure: the "Click to follow <name>" and
// "Click to stop following <name>" buttons, and the /in/ profile link in the card around each one.
await (async () => {
  const MAX_SCROLLS = 8;   // per call, 20 cards each: javascript_tool gives up after 45s
  const MAX_CARDS = 200;   // the newest followers; a weekly run never has this many new ones
  const main = document.querySelector("main");
  if (!/\/people-follow\/followers/.test(location.pathname) || !main) {
    return JSON.stringify({error: `not on the followers page (${location.href}): signed out, or a security check?`});
  }
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const cards = () => {
    const found = new Map();
    for (const b of main.querySelectorAll('button[aria-label^="Click to follow "], button[aria-label^="Click to stop following "]')) {
      let card = b;
      while (card && card !== main && !card.querySelector('a[href*="/in/"]')) card = card.parentElement;
      if (!card || card === main) continue;
      const a = card.querySelector('a[href*="/in/"]');
      const m = a.href.match(/^https:\/\/www\.linkedin\.com\/in\/([^/?#]+)/);
      if (!m || found.has(m[1])) continue;
      // A card starts with its presence dot's text ("Status is online") when they show one
      const lines = (card.innerText || "").split("\n").map(s => s.trim()).filter(Boolean)
        .filter(s => !/^(Follow|Following)$/.test(s) && !/^Status is /.test(s));
      found.set(m[1], {
        url: `https://www.linkedin.com/in/${m[1]}`,
        name: lines[0] || "",
        headline: lines[1] || "",
        following: /^Click to stop following /.test(b.getAttribute("aria-label")),
      });
    }
    return [...found.values()];
  };

  let list = cards(), stuck = 0, done = list.length >= MAX_CARDS;
  for (let i = 0; i < MAX_SCROLLS && !done; i++) {
    const before = list.length;
    window.scrollTo(0, document.documentElement.scrollHeight);
    await sleep(2000 + Math.random() * 1500);
    const more = [...main.querySelectorAll("button")].find(b => (b.innerText || "").trim() === "Show more results" && b.offsetParent !== null);
    if (more) {
      more.click();
      await sleep(1500 + Math.random() * 1000);
    }
    list = cards();
    // No new cards three times running: the end of the list
    stuck = list.length === before ? stuck + 1 : 0;
    done = list.length >= MAX_CARDS || stuck >= 3;
  }
  if (!list.length) return JSON.stringify({error: "no follower cards on the page: has the layout changed?"});
  const follow = list.filter(c => !c.following && c.name).map(({url, name, headline}) => ({url, name, headline}));
  if (done) {
    const old = document.getElementById("gtd-followers");
    if (old) old.remove();
    const pre = document.createElement("pre");
    pre.id = "gtd-followers";
    pre.textContent = ["FOLLOWERS-BEGIN", ...follow.map(c => JSON.stringify(c)), `FOLLOWERS-END ${follow.length}`].join("\n");
    main.prepend(pre);
  }
  return JSON.stringify({done, loaded: list.length, count: follow.length});
})()
