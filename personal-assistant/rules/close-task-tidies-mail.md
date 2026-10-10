# Closing a gtd task tidies its email

Email tied to a gtd task carries a Gmail label `GTD-<task number>` (e.g. `GTD-4652`), in
whichever mailbox the email is in. The mail skill adds the label whenever it creates a task
from an email or links an email to an existing task. When task N is closed, its email is
finished with:

1. **Archive** every thread labelled `GTD-N`, in both mailboxes, and unstar it (see
   unstar-outside-inbox.md):
   - work: search `label:GTD-N` with the Gmail connector, then `unlabel_thread` with
     `INBOX` and `STARRED` (plus the label, step 2);
   - personal: `gmail search 'label:GTD-N'` with gog, then
     `gmail thread modify <id> --remove INBOX,STARRED,GTD-N`.
   Also archive threads whose Gmail link is in `tasks/N/notes.md` but which never got the
   label.
2. **Remove the `GTD-N` label** from those threads, then delete the label itself once no
   thread has it (work: `delete_label`; personal: `gmail labels delete`), so closed tasks
   don't leave labels behind.

This is a standing instruction: Ian closing the task (or approving its close) covers it, with
no separate approval. Say what was done in the close report, e.g. "Archived 2 threads and
removed label GTD-4652".

- Only for tasks that are really closed (`status/closed/N`). Never for tasks moved to
  waiting, someday or background.
- Don't trash or delete any email, only archive it.
- If a mailbox can't be reached, say which, and leave its `GTD-N` label in place so the next
  mail run can finish the job.

## Tasks closed outside Claude

Tasks are also closed by Ian running `gtd close` in a terminal, which can't reach Gmail. So
at the start of each mail run, list the `GTD-<number>` labels in both mailboxes, check each
task's status, and for every task now closed do steps 1 and 2 above. Report it in one line
before the triage list, e.g. "Task 4652 closed: archived 1 thread, removed GTD-4652."
