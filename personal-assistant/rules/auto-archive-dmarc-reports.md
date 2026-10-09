# DMARC reports are archived without asking

DMARC aggregate reports are machine-generated and Ian never reads them. In
the work mailbox they come from `sysadmin@container-solutions.com` with
subjects like `Report domain: engineerbetter.com Submitter: google.com
Report-ID: …`, usually addressed to a systems@ alias.

- Archive them (and unstar, per unstar-outside-inbox.md) as soon as a
  triage run finds them. This is a standing instruction, so no per-run
  approval is needed. It overrides "Never act without approval" for these
  threads only.
- Don't list them under the buckets for approval. Report the count in the
  run's summary instead, e.g. "Auto-archived 2 DMARC reports".
- Match on the subject starting `Report domain:` together with a
  `Submitter:` and `Report-ID:`, or an attached `.xml.gz`/`.zip` aggregate
  report. A human email that merely mentions DMARC is not a report: triage
  it normally.
- A Gmail filter can do this before the inbox (import
  `personal-assistant/filters/dmarc-filter.xml` from Settings → Filters and Blocked Addresses). This
  rule catches any that slip through.
