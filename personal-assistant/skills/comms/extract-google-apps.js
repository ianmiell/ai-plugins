// extract-google-apps.js: run with Claude in Chrome's javascript_tool on Google's linked apps page,
// https://myaccount.google.com/connections?authuser=<address>, to list the third-party apps and
// services Ian has signed in to with Google or given access to his account (see SKILL.md, Google
// apps). javascript_tool truncates long results, so it puts the list at the top of the page, to
// be read with get_page_text: a line "GOOGLE-APPS-BEGIN <account>", one JSON object
// {name, signIn, linked, access: [...]} per app, then "GOOGLE-APPS-END <count>". Pipe those lines
// to google-apps.py record. It returns a short JSON {account, apps: <count>, errors: [...]}, or
// {error} when it isn't the linked apps page (signed out, say).
//
//   signIn  he signs in to it with Google (it gets his name, email and profile picture)
//   linked  a "Linked account" (his account on that service is linked to Google's)
//   access  what Google's page says it can do with his account, one line each, e.g. "See and
//           download any calendar that you can access using your Google Calendar"; empty when
//           it only has Sign in with Google
//
// It only reads. It fetches the list page and each app's overview page in the background (the
// server renders them in full, whatever filter the page on screen has), so nothing is clicked,
// opened or removed. The overview links are one-off tokens that change on every load, so apps are
// identified by name; two entries with one name (two OpenAI clients) are merged. Checked
// November 2026.
await (async () => {
  const who = document.querySelector('[aria-label*="@"]')?.getAttribute('aria-label') || '';
  const account = (who.match(/\(([^)]+@[^)]+)\)/) || [])[1];
  if (!/\/connections$/.test(location.pathname) || !account) {
    return JSON.stringify({error: `not the linked apps page (${location.hostname}${location.pathname})`});
  }
  const unescape = s => s.replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>').replace(/&amp;/g, '&');
  const texts = html => unescape(html.replace(/<[^>]+>/g, '\n')).split('\n').map(s => s.trim()).filter(Boolean);
  const get = url => fetch(url, {credentials: 'include'}).then(r => {
    if (!r.ok) throw new Error(`${r.status} on ${new URL(url).pathname}`);
    return r.text();
  });
  const list = await get(location.pathname);
  const rows = (list.match(/<a[^>]*data-provider-index[^>]*>[\s\S]*?<\/a>/g) || []).map(a => ({
    name: texts(a)[0],
    url: new URL(unescape((a.match(/href="([^"]+)"/) || [])[1] || ''), location.href).href,
  })).filter(r => r.name);
  if (!rows.length) return JSON.stringify({error: 'no apps found on the page (signed out, or the layout changed?)'});
  // Headings, explanations and icon names on an overview page; what's left are the access lines.
  const noise = /^(Sign in with Google|See details|Delete all|How Google helps you|When you use|To use some|Remove all links|See something suspicious|Report this app|Linked account)|has some access to your Google Account|^[a-z_]+$/;
  const apps = {};
  const errors = [];
  for (let i = 0; i < rows.length; i += 6) {
    await Promise.all(rows.slice(i, i + 6).map(async r => {
      const app = apps[r.name] = apps[r.name] || {name: r.name, signIn: false, linked: false, access: []};
      let html;
      try {
        html = (await get(r.url)).replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/g, ' ');
      } catch (e) {
        errors.push(`${r.name}: ${e.message}`);
        return;
      }
      for (const art of html.match(/<article[\s\S]*?<\/article>/g) || []) {
        const t = texts(art);
        const head = t.join(' ');
        if (/How Google helps you sign in/.test(head)) { app.signIn = true; continue; }
        // A linked account is Google reaching into the other service ("Google has some access
        // to your Netflix account"), not the app reaching into Google: flag it, list nothing.
        if (/^Google has some access|You linked your Google Account/.test(head)) { app.linked = true; continue; }
        for (const line of t) {
          if (!noise.test(line) && line !== 'See your profile info' && line.length < 200 && !app.access.includes(line)) {
            app.access.push(line);
          }
        }
      }
    }));
  }
  const found = Object.values(apps);
  document.getElementById('google-apps-out')?.remove();
  const pre = document.createElement('pre');
  pre.id = 'google-apps-out';
  pre.textContent = [`GOOGLE-APPS-BEGIN ${account}`, ...found.map(a => JSON.stringify(a)),
    `GOOGLE-APPS-END ${found.length}`].join('\n');
  (document.querySelector('main, [role=main]') || document.body).prepend(pre);
  return JSON.stringify({account, apps: found.length, errors});
})()
