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
// It only ever clicks Connect in the profile's top card (directly or in its More menu), and Send in
// the invitation dialog that opens. The sidebar ("People also viewed") has Connect buttons of its
// own, so everything is looked up inside the top card, the innermost <section> holding the name: the
// <h1>, or since the October 2026 layout the first <h2> in <main> (an outer <section> holds the
// activity feed too). Dialogs and toasts are position: fixed, so have no offsetParent: visibility
// is getClientRects().
await (async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const label = e => ((e.innerText || "").trim().split("\n")[0] || e.getAttribute("aria-label") || "").trim();
  const done = (status, detail) => JSON.stringify(detail ? {status, detail} : {status});
  const LIMIT = /invitation limit|reached the (weekly|maximum)|too many (pending )?invitations/i;
  // Dialogs and menus can be drawn in a shadow root (since October 2026, the one on #interop-outlet)
  const inPage = sel => [document, ...[...document.querySelectorAll("*")].filter(e => e.shadowRoot).map(e => e.shadowRoot)]
    .flatMap(root => [...root.querySelectorAll(sel)]);
  const visible = e => e.isConnected && e.getClientRects().length > 0;
  const toasts = () => inPage('[role="alert"], [role="status"], .artdeco-toast-item').filter(visible)
    .map(e => e.innerText || "").join("\n");

  // Pace: a few seconds on each profile before doing anything, as a person would
  await sleep(6000 + Math.random() * 4000);
  const main = document.querySelector("main");
  const name = main && (main.querySelector("h1") || main.querySelector("h2"));
  const top = name && [...main.querySelectorAll("section")].filter(s => s.contains(name)).pop();
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
    const items = inPage('[role="menuitem"]').filter(visible);
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
  connect.click();
  await sleep(2000 + Math.random() * 1000);

  // An open chat window is a dialog too (with a Send button of its own), so take the one about the
  // invitation: it offers Send without a note, asks for an email address or says the limit is reached
  const dialogs = inPage('[role="dialog"], [role="alertdialog"]').filter(visible);
  const dialog = dialogs.find(d => [...d.querySelectorAll("button")].some(b => /^Send without a note$/.test(b.getAttribute("aria-label") || label(b)))
      || d.querySelector('input[type="email"]') || LIMIT.test(d.innerText || ""))
    || dialogs.find(d => /invitation/i.test(d.innerText || ""))
    || dialogs[0];
  const dismiss = () => {
    const x = dialog && [...dialog.querySelectorAll("button")].find(b => /^(Dismiss|Close|Cancel)$/.test(b.getAttribute("aria-label") || label(b)));
    if (x) x.click();
    return !!x;
  };
  if (!dialog) {
    // Some profiles send straight away, without a dialog
    return /Invitation sent/i.test(toasts()) ? done("sent") : done("unexpected", "no invitation dialog opened");
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
  const send = [...dialog.querySelectorAll("button")].find(b => /^Send without a note$/.test(label(b)) || /^Send without a note$/.test(b.getAttribute("aria-label") || ""))
    || [...dialog.querySelectorAll("button")].find(b => /^Send( now| invitation)?$/.test(b.getAttribute("aria-label") || label(b)) && !b.disabled);
  if (!send) {
    const first = text.split("\n").map(s => s.trim()).find(Boolean) || "";
    dismiss();
    return done("unexpected", `dialog without a Send button: "${first.slice(0, 80)}"`);
  }
  send.click();
  await sleep(2500 + Math.random() * 1000);

  const after = toasts() + "\n" + (visible(dialog) ? dialog.innerText || "" : "");
  if (LIMIT.test(after)) return done("limit", after.split("\n").find(s => LIMIT.test(s)));
  if (visible(dialog) && dialog.contains(send)) return done("unexpected", "the invitation dialog is still open after Send");
  if (/Invitation sent/i.test(after)) return done("sent");
  return done("unexpected", "the dialog closed but LinkedIn didn't say \"Invitation sent\": check the profile");
})()
