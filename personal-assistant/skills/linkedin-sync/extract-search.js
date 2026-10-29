// extract-search.js: run on a LinkedIn people search (https://www.linkedin.com/search/results/people/
// ?keywords=...) with Claude in Chrome's javascript_tool (see SKILL.md step 3b). Nothing to replace.
//
// Waits a few seconds, as a person reading the results would, then reads the first page of results.
// Returns JSON, small enough to pass straight to `linkedin-state.py match`:
//   {results: [{url, name, headline, degree}]}   (empty when LinkedIn found nobody)
//   {limit: true, error}                          LinkedIn's monthly search limit: stop searching
//   {error}                                       not a search page (signed out, a security check?)
// It clicks nothing. Class names on the page are generated, so it goes by structure: each /in/
// profile link, and the card around it (its <li>, or the largest ancestor holding no other profile).
// "LinkedIn Member" results (outside Ian's network) have no /in/ link, so they're left out.
await (async () => {
  const MAX = 10;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  await sleep(3000 + Math.random() * 3000);
  const main = document.querySelector("main");
  if (!/^\/search\/results\/people/.test(location.pathname) || !main) {
    return JSON.stringify({error: `not a people search page (${location.href}): signed out, or a security check?`});
  }
  if (/commercial use limit|reached the monthly limit for profile searches/i.test(main.innerText)) {
    return JSON.stringify({limit: true, error: "LinkedIn's search limit is reached"});
  }
  const slugOf = a => (a.href.match(/^https:\/\/www\.linkedin\.com\/in\/([^/?#]+)/) || [])[1];
  const cardOf = a => {
    const li = a.closest("li");
    if (li && main.contains(li)) return li;
    let card = a;
    while (card.parentElement && card.parentElement !== main &&
           [...card.parentElement.querySelectorAll('a[href*="/in/"]')].every(x => slugOf(x) === slugOf(a))) {
      card = card.parentElement;
    }
    return card;
  };
  const NOISE = /^(Connect|Message|Follow|Following|Pending|View .*profile|Status is .*|.*mutual connections?|\W*(1st|2nd|3rd\+?)( degree connection)?)$/i;
  const found = new Map();
  for (const a of main.querySelectorAll('a[href*="/in/"]')) {
    const slug = slugOf(a);
    if (!slug || found.has(slug) || found.size >= MAX) continue;
    // The visible name is in an aria-hidden span; the link text also has "View <name>'s profile"
    const name = ((a.querySelector('span[aria-hidden="true"]') || a).innerText || "").split("\n")[0].trim();
    if (!name || /^LinkedIn Member$/i.test(name)) continue;
    const card = cardOf(a);
    const text = card.innerText || "";
    const degree = (text.match(/\b(1st|2nd|3rd\+?)\b/) || [])[1] || "";
    const headline = [...new Set(text.split("\n").map(s => s.replace(/^[•·]\s*/, "").trim()))]
      .filter(s => s && s !== name && !NOISE.test(s)).join(" · ").slice(0, 300);
    found.set(slug, {url: `https://www.linkedin.com/in/${slug}`, name, headline, degree});
  }
  if (!found.size && !/no results found/i.test(main.innerText)) {
    // Results still loading, or a layout this doesn't know: say so rather than report "nobody"
    return JSON.stringify({error: "no profile links on the results page: still loading, or has the layout changed?"});
  }
  return JSON.stringify({results: [...found.values()]});
})()
