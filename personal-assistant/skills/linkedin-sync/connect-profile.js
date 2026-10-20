// connect-profile.js: run on a LinkedIn profile (https://www.linkedin.com/in/...) with Claude in
// Chrome's javascript_tool, to send that person a connection request without a note (see SKILL.md
// step 4). Returns JSON {status, detail?}, where status is one of:
//   sent        the invitation went (LinkedIn said "Invitation sent")
//   connected   already a 1st-degree connection: nothing done
//   pending     an invitation is already waiting: nothing done
//   no-connect  no Connect on the profile (some only offer Follow): nothing done
//   needs-email LinkedIn wants their email address: the dialog was dismissed, nothing sent
//   limit       LinkedIn says the invitation limit is reached: stop sending this run
//   unexpected  a dialog or page this doesn't know: dismissed if possible; stop and look
//   error       not a profile page (signed out, or a security check?): stop
// It only ever clicks Connect in the profile's top card (directly or in its More menu), and Send
// without a note in the invitation dialog that opens. The rest of the page ("People similar to",
// "More profiles for you") has Connect buttons of its own, so the top card is found first: the
// smallest <section> whose first heading is the page's first heading, the name. LinkedIn renders menus and
// dialogs in shadow roots, and dialogs are position: fixed (no offsetParent), so lookups go through
// every shadow root and visibility is getClientRects().
await (async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const label = e => ((e.innerText || "").trim().split("\n")[0] || e.getAttribute("aria-label") || "").trim();
  const done = (status, detail) => JSON.stringify(detail ? {status, detail} : {status});
  const visible = e => e.isConnected && e.getClientRects().length > 0;
  const all = selector => {
    const roots = [document];
    for (const e of document.querySelectorAll("*")) if (e.shadowRoot) roots.push(e.shadowRoot);
    return roots.flatMap(r => [...r.querySelectorAll(selector)]).filter(visible);
  };
  const dialogs = () => all('[role="dialog"], [role="alertdialog"], dialog');
  const toasts = () => all('[role="alert"], [role="status"], .artdeco-toast-item').map(e => (e.innerText || "").trim()).join("\n");
  const LIMIT = /invitation limit|reached the (weekly|maximum)|too many (pending )?invitations/i;

  // Pace: a few seconds on each profile before doing anything, as a person would
  await sleep(4000 + Math.random() * 3000);
  const main = document.querySelector("main");
  // The name is the first heading in <main> (an h2, and not always the title's wording: "Jo (Joe) Bloggs")
  const name = main && main.querySelector("h1, h2");
  const tops = name ? [...main.querySelectorAll("section")].filter(s => s.querySelector("h1, h2") === name) : [];
  const top = tops.filter(s => !tops.some(o => o !== s && s.contains(o))).pop();
  if (!/^\/in\//.test(location.pathname) || !top) return done("error", `not a profile page (${location.href})`);
  const degree = (top.innerText.match(/·\s*(1st|2nd|3rd\+?)/) || [])[1] || "";
  if (degree === "1st") return done("connected");
  const buttons = () => [...top.querySelectorAll("button, a")];
  if (buttons().some(b => /^Pending$/.test(label(b)) || /^Pending/.test(b.getAttribute("aria-label") || ""))) {
    return done("pending");
  }

  // Connect is a button in the top card, or an item in its More menu
  let connect = buttons().find(b => label(b) === "Connect" || /^Invite .+ to connect$/.test(b.getAttribute("aria-label") || ""));
  if (!connect) {
    const more = buttons().find(b => label(b) === "More" || b.getAttribute("aria-label") === "More actions");
    if (!more) return done("no-connect", "no Connect or More in the top card");
    more.click();
    await sleep(1200 + Math.random() * 800);
    const items = all('[role="menuitem"]');
    if (items.some(e => /^(Pending|Withdraw)/.test(label(e)))) {
      more.click();
      return done("pending");
    }
    if (items.some(e => label(e) === "Remove connection")) {
      more.click();
      return done("connected");
    }
    connect = items.find(e => label(e) === "Connect" || /^Invite .+ to connect$/.test(e.getAttribute("aria-label") || ""));
    if (!connect) {
      more.click();
      return done("no-connect", "no Connect in the More menu");
    }
  }
  const before = new Set(dialogs());
  connect.click();
  await sleep(2000 + Math.random() * 1000);

  // The dialog Connect opened: one that wasn't there before (the messaging overlay is a dialog too)
  const dialog = dialogs().find(d => !before.has(d));
  const dismiss = () => {
    const x = dialog && [...dialog.querySelectorAll("button")].find(b => /^(Dismiss|Close|Cancel)$/.test(b.getAttribute("aria-label") || label(b)));
    if (x) x.click();
    return !!x;
  };
  if (!dialog) {
    if (/Invitation sent/i.test(toasts())) return done("sent");
    return done("unexpected", "no invitation dialog opened");
  }
  const text = dialog.innerText || "";
  if (LIMIT.test(text)) {
    dismiss();
    return done("limit", text.split("\n").find(s => LIMIT.test(s)));
  }
  if (dialog.querySelector('input[type="email"]') || /their email|email address/i.test(text)) {
    dismiss();
    return done("needs-email");
  }
  const send = [...dialog.querySelectorAll("button")].find(b => label(b) === "Send without a note" || b.getAttribute("aria-label") === "Send without a note")
    || [...dialog.querySelectorAll("button")].find(b => /^Send( now| invitation)?$/.test(b.getAttribute("aria-label") || label(b)) && !b.disabled);
  if (!send) {
    const first = text.split("\n").map(s => s.trim()).find(Boolean) || "";
    dismiss();
    return done("unexpected", `dialog without a Send button: "${first.slice(0, 80)}"`);
  }
  send.click();
  await sleep(2500 + Math.random() * 1000);

  const after = toasts() + "\n" + dialogs().filter(d => !before.has(d)).map(d => d.innerText || "").join("\n");
  if (LIMIT.test(after)) return done("limit", after.split("\n").find(s => LIMIT.test(s)));
  if (visible(dialog) && dialog.contains(send)) return done("unexpected", "the invitation dialog is still open after Send");
  if (/Invitation sent/i.test(after)) return done("sent");
  return done("unexpected", "the dialog closed but LinkedIn didn't say \"Invitation sent\": check the profile");
})()
