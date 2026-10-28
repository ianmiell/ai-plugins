// follow-follower.js: run on the followers page, after extract-followers.js has loaded it, with
// Claude in Chrome's javascript_tool, after replacing __URL__ with a follower's profile URL from its
// output (see SKILL.md step 5b). Follows that one person back. Returns JSON {status, detail?}:
//   followed    the button turned into Following
//   already     Ian already follows them: nothing done
//   missing     their card isn't loaded on the page (run extract-followers.js again): nothing done
//   not-followed  clicked, but the button stayed Follow (seen October 2026 on some followers whose
//               profile link is a bare member id, /in/ACoAA...): skip them, Ian can try by hand
//   limit       LinkedIn says too many follows: stop following this run
//   unexpected  a dialog opened: stop and look
//   error       not the followers page (signed out, or a security check?): stop
// Its only click is "Click to follow <name>" in that person's card. It never clicks Following
// (that unfollows). Dialogs and toasts are position: fixed, so have no offsetParent: visibility is
// getClientRects().
await (async () => {
  const URL = "__URL__";
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const done = (status, detail) => JSON.stringify(detail ? {status, detail} : {status});
  const LIMIT = /limit|too many|try again later|can.t follow/i;
  const visible = e => e.isConnected && e.getClientRects().length > 0;
  const main = document.querySelector("main");
  if (!/\/people-follow\/followers/.test(location.pathname) || !main) {
    return done("error", `not on the followers page (${location.href})`);
  }
  const slug = (URL.match(/\/in\/([^/?#]+)/) || [])[1];
  if (!slug || URL.includes("__")) return done("error", "__URL__ was not replaced with a profile URL");

  // Looked up afresh each time: LinkedIn can redraw the card when its button changes
  const findCard = () => {
    for (const a of main.querySelectorAll('a[href*="/in/"]')) {
      const m = a.href.match(/^https:\/\/www\.linkedin\.com\/in\/([^/?#]+)/);
      if (!m || decodeURIComponent(m[1]) !== decodeURIComponent(slug)) continue;
      let c = a;
      while (c && c !== main && !c.querySelector('button[aria-label^="Click to "]')) c = c.parentElement;
      if (c && c !== main) return c;
    }
    return null;
  };
  const card = findCard();
  if (!card) return done("missing");
  if (card.querySelector('button[aria-label^="Click to stop following "]')) return done("already");
  const follow = card.querySelector('button[aria-label^="Click to follow "]');
  if (!follow) return done("unexpected", "no Follow button in their card");

  // Pace: look at the card a few seconds first, as a person would
  follow.scrollIntoView({block: "center"});
  await sleep(4000 + Math.random() * 3000);
  follow.click();

  // An open chat window (the Messaging overlay) is a dialog too: leave it out
  const dialogs = () => [...document.querySelectorAll('[role="dialog"], [role="alertdialog"]')]
    .filter(d => visible(d) && d.getAttribute("aria-label") !== "Messaging" && !d.closest('[class*="msg-overlay"]'));
  for (let i = 0; i < 4; i++) {
    await sleep(1500 + Math.random() * 500);
    const notes = [...document.querySelectorAll('[role="alert"], .artdeco-toast-item'), ...dialogs()]
      .filter(visible).map(e => e.innerText || "").join("\n");
    if (LIMIT.test(notes)) return done("limit", notes.split("\n").find(s => LIMIT.test(s)));
    const now = findCard();
    if (now && now.querySelector('button[aria-label^="Click to stop following "]')) return done("followed");
  }
  const dialog = dialogs()[0];
  if (dialog) return done("unexpected", `a dialog opened: "${(dialog.innerText || "").trim().split("\n")[0].slice(0, 80)}"`);
  return done("not-followed", "the button didn't turn into Following");
})()
