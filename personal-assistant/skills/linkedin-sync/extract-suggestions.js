// extract-suggestions.js: run on https://www.linkedin.com/mynetwork/grow/ with Claude in Chrome's
// javascript_tool (see SKILL.md step 5). Nothing to replace.
//
// Scrolls the page (it lives in <main>, not the window) a few times at a human pace, so the
// suggestion sections ("<Name>'s connections you may know", "Suggestions for you", ...) load, and
// reads every card that offers Connect. Returns JSON:  {loaded, count}  or  {error}
// It then replaces the page's <main> with the suggestions, most mutual connections first, one JSON
// object {url, name, headline, mutual} per line between SUGGESTIONS-BEGIN and SUGGESTIONS-END
// <count> lines, to be read with get_page_text. The only click is Load more at the foot of the list
// (in a narrow window): the invitations go from each person's profile with connect-profile.js.
// Class names on the page are generated, so it goes by structure: the "Invite <name> to connect"
// buttons, and the /in/ profile link in the card around each one.
await (async () => {
  const MAX_SCROLLS = 6;  // ~30 cards each
  const MAX_CARDS = 150;
  const main = document.querySelector("main");
  if (!/\/mynetwork\/grow/.test(location.pathname) || !main) {
    return JSON.stringify({error: `not on the Grow page (${location.href}): signed out, or a security check?`});
  }
  const cards = () => {
    const found = new Map();
    for (const b of main.querySelectorAll('button[aria-label^="Invite "][aria-label$=" to connect"]')) {
      let card = b;
      while (card && card !== main && !card.querySelector('a[href*="/in/"]')) card = card.parentElement;
      if (!card || card === main) continue;
      const m = card.querySelector('a[href*="/in/"]').href.match(/^https:\/\/www\.linkedin\.com\/in\/([^/?#]+)/);
      if (!m || found.has(m[1])) continue;
      const lines = (card.querySelector('a[href*="/in/"]').innerText || "").split("\n").map(s => s.trim()).filter(Boolean);
      // "Sam and 46 other mutual connections", "Sam is a mutual connection"
      const others = (card.innerText.match(/(\d+) other mutual connections?/) || [])[1];
      found.set(m[1], {
        url: `https://www.linkedin.com/in/${m[1]}`,
        name: lines[0] || "",
        headline: lines.slice(1).join(" "),
        mutual: others ? Number(others) + 1 : /mutual connection/.test(card.innerText) ? 1 : 0,
      });
    }
    return [...found.values()];
  };
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  let list = cards(), stuck = 0;
  for (let i = 0; i < MAX_SCROLLS && list.length < MAX_CARDS && stuck < 2; i++) {
    const before = list.length;
    main.scrollTo(0, main.scrollHeight);
    await sleep(1500 + Math.random() * 1000);
    // Some layouts load more on scrolling, others (a narrow window) end in a Load more button
    const more = [...main.querySelectorAll("button")].find(b => (b.innerText || "").trim() === "Load more" && b.offsetParent !== null);
    if (more) more.click();
    await sleep(2000 + Math.random() * 1500);
    list = cards();
    stuck = list.length === before ? stuck + 1 : 0;
  }
  if (!list.length) return JSON.stringify({error: "no suggestions with Connect on the page: has the layout changed?"});
  const people = list.filter(c => c.name).sort((a, b) => b.mutual - a.mutual);
  const pre = document.createElement("pre");
  pre.textContent = ["SUGGESTIONS-BEGIN", ...people.map(c => JSON.stringify(c)), `SUGGESTIONS-END ${people.length}`].join("\n");
  main.replaceChildren(pre);
  return JSON.stringify({loaded: list.length, count: people.length});
})()
