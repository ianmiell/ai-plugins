# Emails linked to a gtd task get a GTD-N label

When an email thread is linked to a gtd task, label the thread `GTD-<N>`,
where N is the task number (e.g. task 4646 → label `GTD-4646`).

- This applies both ways: when a task is created from an email, and when an
  email is found to relate to an existing task (in triage, or while working
  on a task in the gtd skill).
- Labels are per mailbox. Apply it in the mailbox the thread lives in. If the
  same email is in both mailboxes, label both.
- Create the label if it doesn't exist yet. This rule is standing permission
  to create `GTD-<N>` labels, so don't ask first (this overrides the mail
  skill's "ask first the first time for each mailbox").
- Apply the label as part of the approved task action (create task, add a
  note, link to task N). It doesn't need a separate approval, but say in the
  report which threads were labelled.
- The label stays when the thread is archived (see
  archive-emails-with-tasks.md), so `label:GTD-<N>` finds the task's emails
  later. Don't remove it when the task closes.
- A thread can carry more than one `GTD-` label if it relates to several
  tasks.
