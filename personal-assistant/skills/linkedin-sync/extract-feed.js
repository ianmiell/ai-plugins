// extract-feed.js: run on https://www.linkedin.com/feed/network/ (the feed's Network tab: posts
// from Ian's connections and the people he follows) with Claude in Chrome's javascript_tool, after
// replacing __SINCE__ with the last sync time as an ISO date-time such as 2026-10-13T08:30:00Z
// (see SKILL.md step 5c).
//
// Scrolls the feed (it lives in <main>, not the window) at a human pace and reads each post by a
// person: who wrote it (their profile link, name, degree, and an "Open to work" badge), who brought
// it into the feed ("Jane Doe commented on this"), its words, its age and its reactions, comments
// and reposts. The words are cut at 300 characters (and at LinkedIn's own "… more"), enough to tell
// what the post is about. Returns JSON:
//   {done, loaded, count}  or  {error}
// done is false if it stopped after MAX_SCROLLS this call: run it again and it carries on (the
// posts read so far are kept in the page, as the feed drops posts that scroll far out of view).
// It stops at MAX_POSTS, when the last few posts read are all from before SINCE, or at the end of
// the feed. The Network feed is not in time order, so in practice it reads MAX_POSTS in about two
// calls, most of them from the last day or two. When done, it replaces the page's <main> with the
// posts since SINCE, one JSON object
//   {url, name, openToWork, degree, context, age, reactions, comments, reposts, text}
// per line between FEED-BEGIN and FEED-END <count> lines, to be read with get_page_text.
// Ads ("Promoted") and posts by companies are left out. The page gives relative ages ("3h",
// "2d"), so a post counts as since SINCE if it could have been after it.
// It clicks nothing: no reactions, comments, "… more" or Follow. Class names on the page are
// generated, so it goes by structure: the hidden "Feed post" heading of each post, the /in/ links
// in it, and the counts in its Reaction, Comment and Repost buttons.
await (async () => {
  const SINCE = new Date("__SINCE__");
  const MAX_SCROLLS = 8;   // per call: javascript_tool gives up after 45s
  const MAX_POSTS = 120;
  const UNITS = {m: 60e3, h: 3600e3, d: 86400e3, w: 7 * 86400e3, mo: 30 * 86400e3, y: 365 * 86400e3};
  const main = document.querySelector("main");
  if (!/^\/feed/.test(location.pathname) || !main) {
    return JSON.stringify({error: `not on the feed (${location.href}): signed out, or a security check?`});
  }
  if (isNaN(SINCE)) return JSON.stringify({error: "__SINCE__ was not replaced with an ISO date-time"});
  if (main.innerText.startsWith("FEED-BEGIN")) return JSON.stringify({error: "the list is already written: read it with get_page_text"});
  const now = Date.now();
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const slugUrl = href => {
    const m = (href || "").match(/^https:\/\/www\.linkedin\.com\/in\/([^/?#]+)/);
    return m ? `https://www.linkedin.com/in/${m[1]}` : null;
  };
  const count = (post, re) => {
    const b = [...post.querySelectorAll("button")].find(b => re.test(b.getAttribute("aria-label") || ""));
    const n = b && (b.innerText || "").match(/(\d[\d,.]*)\s*(K)?/);
    return n ? Math.round(parseFloat(n[1].replace(/,/g, "")) * (n[2] ? 1000 : 1)) : 0;
  };
  const read = post => {
    const lines = (post.innerText || "").split("\n").map(s => s.trim()).filter(s => s && s !== "​" && s !== "Feed post");
    if (lines.some(s => /^Promoted$/.test(s))) return null;
    // The author's link is the one showing their degree ("Jane Doe • 1st"), labelled inside
    // "Jane Doe Premium Profile 1st"; other /in/ links in the header are the people who brought
    // the post into the feed ("John Roe commented on this")
    const DEGREE = /•\s*(1st|2nd|3rd\+?|Following)\b/;
    const links = [...post.querySelectorAll('a[href*="/in/"]')];
    const author = links.find(a => DEGREE.test(a.innerText || "")) || null;
    const url = author && slugUrl(author.href);
    if (!url) return null;  // a company's post, or a layout this doesn't know
    const label = [...author.querySelectorAll("[aria-label]")].map(e => e.getAttribute("aria-label"))
      .find(l => /\bProfile\b/.test(l)) || "";
    const shown = label.replace(/\s+((Premium|Verified)\s+)*Profile\b.*$/, "").trim()
      || (author.innerText || "").split("\n")[0].trim();
    // "Jane Doe, Open to work": the badge is news in itself
    const openToWork = /,\s*Open to work\b/i.test(shown);
    const name = shown.replace(/,\s*Open to work\b/i, "").trim();
    const at = lines.findIndex(s => s === shown || s.startsWith(name));
    const context = at > 0 ? lines.slice(0, at).join(" ").slice(0, 160) : "";
    const degree = (lines.find(s => /^•\s*(1st|2nd|3rd\+?|Following)$/.test(s)) || "").replace(/^•\s*/, "");
    const ageAt = lines.findIndex(s => /^(\d+)\s*(mo|m|h|d|w|y)\b(\s*•.*)?$/.test(s));
    const m = ageAt >= 0 && lines[ageAt].match(/^(\d+)\s*(mo|m|h|d|w|y)\b/);
    // The words: after the age line (or the header), up to the counts and the action bar
    const body = lines.slice(ageAt >= 0 ? ageAt + 1 : at + 1)
      .filter(s => !/^(Follow|Visit my website|… more|…see more|\d[\d,.]*K?|Like|Comment|Repost|Send)$/.test(s));
    return {url, name, openToWork, degree, context, age: m ? `${m[1]}${m[2]}` : "",
      at: m ? now - Number(m[1]) * UNITS[m[2]] : now,
      reactions: count(post, /^Reaction button/), comments: count(post, /^Comment/), reposts: count(post, /^Repost/),
      text: body.join(" ").replace(/\s+/g, " ").slice(0, 300)};
  };
  const posts = () => [...main.querySelectorAll("h2")].filter(h => (h.innerText || "").trim() === "Feed post").map(h => {
    let p = h.parentElement;
    while (p && p !== main && !p.querySelector('button[aria-label^="Reaction button"]')) p = p.parentElement;
    return p && p !== main ? p : null;
  }).filter(Boolean);

  const seen = window.__gtdFeed = window.__gtdFeed || new Map();
  const collect = () => {
    for (const p of posts()) {
      const r = read(p);
      if (r) seen.set(`${r.url} ${r.text.slice(0, 60)}`, r);
    }
  };
  const list = () => [...seen.values()];
  const finished = () => {
    const l = list();
    return l.length >= MAX_POSTS || (l.length >= 8 && l.slice(-5).every(r => r.at < SINCE));
  };
  collect();
  let done = finished(), stuck = 0;
  for (let i = 0; i < MAX_SCROLLS && !done; i++) {
    const before = seen.size;
    // The feed scrolls in <main> (November 2026), not the window: scroll both
    main.scrollTo(0, main.scrollHeight);
    window.scrollTo(0, document.documentElement.scrollHeight);
    await sleep(2500 + Math.random() * 2000);
    collect();
    // No new posts three times running: the end of the feed
    stuck = seen.size === before ? stuck + 1 : 0;
    done = finished() || stuck >= 3;
  }
  const recent = list().filter(r => r.at >= SINCE);
  if (done) {
    const pre = document.createElement("pre");
    pre.textContent = ["FEED-BEGIN", ...recent.map(({at, ...r}) => JSON.stringify(r)), `FEED-END ${recent.length}`].join("\n");
    main.replaceChildren(pre);
    window.__gtdFeed = null;
  }
  return JSON.stringify({done, loaded: seen.size, count: recent.length});
})()
