// preflight.js: run with Claude in Chrome's javascript_tool on a tab just navigated to a LinkedIn
// page, before the step's own script (see SKILL.md, Chrome checks). Nothing to replace.
// Returns JSON {ok: true, href} or {ok: false, href, reason}. It only reads: no clicks, no scrolling.
// When javascript_tool itself fails with "Cannot access a chrome-extension:// URL of different
// extension", this never ran: another extension (e.g. Adobe Acrobat) has taken over the tab.
(() => {
  const href = location.href;
  const no = reason => JSON.stringify({ok: false, href, reason});
  if (location.protocol !== "https:" || !/(^|\.)linkedin\.com$/.test(location.hostname)) {
    return no("the tab isn't on linkedin.com: another extension or a redirect has taken it elsewhere");
  }
  const text = document.body ? (document.body.innerText || "").slice(0, 3000) : "";
  if (/^\/(login|uas\/login|checkpoint|authwall|signup)/.test(location.pathname) ||
      document.querySelector('input[type="password"]')) {
    return no("a sign-in form or security check: never sign in; stop and tell Ian");
  }
  if (/captcha|verify you.re a human|security verification|let.s do a quick security check/i.test(text)) {
    return no("a security check: stop and tell Ian");
  }
  if (!document.querySelector("main")) return no("no <main> on the page yet: wait a few seconds and run it again");
  return JSON.stringify({ok: true, href});
})()
