# Emails with a gtd task should be archived

If an email thread has a gtd task raised against it, suggest archiving the
email. The task now tracks the work and holds the link back to the email, so
the email doesn't need to stay in the inbox.

- This applies whether the task was created in this run or already existed.
  A task "has been raised against" a thread when an open task (`status/todo`,
  `status/waiting`) contains that thread's Gmail link or id, or clearly
  covers the same request (same sender and subject).
- In the triage list, tag the thread `🗂 task N` and recommend
  `→ Archive (tracked in task N)`.
- It's a suggestion. Archive only once Ian approves, like any other action.
  When archived, the email is also unstarred (see unstar-outside-inbox.md).
- This rule overrides star-processed-inbox.md for these threads. Don't
  recommend keeping them starred in the inbox just because they were
  processed.
