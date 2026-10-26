# ai-plugins

## Plugins

This repo is also a Claude Code plugin marketplace (`.claude-plugin/marketplace.json`).

- [`personal-assistant`](personal-assistant/README.md): Ian Miell's personal assistant
- [`ian-voice`](ian-voice/README.md): Ian Miell's public technical writing voice (`/ian-voice:tech-writing`); `VOICE.md` also works pasted into any LLM
- [`container-solutions`](container-solutions/README.md): Container Solutions work tools; `/container-solutions:drive` checks the content catalog against Google Drive and finds misfiled documents

```text
/plugin marketplace add ianmiell/ai-plugins
/plugin install personal-assistant@ianmiell
/plugin install ian-voice@ianmiell
/plugin install container-solutions@ianmiell
```
