# container-solutions

Tools for Ian Miell's work at Container Solutions.

## Layout

```
README.md                      - this file
skills/drive/SKILL.md          - /drive: the content catalog against the shared drives and the blog; misfiled documents in the shared drives
skills/drive/default-config.json - the shared drives, customer and all-hands settings, content and filing rules (generic; Ian's own go in ~/.claude/container-solutions/drive.json)
scripts/drive-inventory.py     - cache a full listing of each shared drive via gog (refresh, status, tree, find, export)
scripts/catalog-diff.py        - read the catalog (values and hyperlinks), diff it against the drives; `blog` against the blog sitemap
scripts/filing-check.py        - flag files that look misfiled (root, customer, allhands, rule, mydrive, stray)
scripts/drive-decide.py        - record Ian's decisions on flagged files so they don't come up again
scripts/cs_drive.py            - shared helpers (config, read-only gog, cache, Drive ID parsing)
tests/                         - `python3 -m unittest discover -s container-solutions/tests`: the scripts against made-up fixtures and a fake gog
```

## Setup

The scripts need gog (`brew install gogcli`) logged in to the work account
with Drive and Sheets:

```
gog auth add ian.miell@container-solutions.com --services drive,sheets
```

They always run gog with `--readonly`. Moves happen through the claude.ai
Google Drive connector, and only after Ian approves them.

This repo is public, so nothing about CS's files is kept in it. The
catalog ID, the drive listings and Ian's decisions live in
`~/.claude/container-solutions/` (`CS_STATE` points the scripts
elsewhere, which is what the tests do).
