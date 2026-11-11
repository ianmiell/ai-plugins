#!/usr/bin/env python3
"""Fork the pairing exercise for a candidate, and take their access away afterwards.

  interview-fork.py [HANDLE]             fork ContainerSolutions/API-Exercise as
                                         ContainerSolutions/API-Exercise-<HANDLE> and give HANDLE write access
  interview-fork.py [HANDLE] --remove    remove HANDLE's access (and any pending invitation) after the session
  interview-fork.py [HANDLE] --dry-run   show what would happen, change nothing
  interview-fork.py --list               show every API-Exercise-<handle> fork and who still has access

HANDLE is the candidate's GitHub handle; a leading @ or a github.com/ URL is accepted. If it
isn't given, the script asks for it on the terminal. With no terminal (as when the interview
skill runs it) it exits with status 2 and says the handle is needed, so ask Ian or Ivana and
run it again. It checks the handle is a real GitHub user before changing anything, and it
asks y/n before forking or removing unless --yes is given. Re-running is safe: an existing
fork is reused, and access that is already there is left alone.

Needs the gh CLI, logged in with rights over the ContainerSolutions org. See the
"Recruitment process" doc, Step 3, for why.
"""

import argparse
import json
import re
import subprocess
import sys
import time

ORG = "ContainerSolutions"
SOURCE = "API-Exercise"
HANDLE_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")


def gh(*args, check=True):
    """Run gh and return (returncode, stdout, stderr)."""
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and p.returncode:
        sys.exit(f"gh {' '.join(args)} failed:\n{p.stderr.strip() or p.stdout.strip()}")
    return p.returncode, p.stdout, p.stderr


def clean_handle(raw):
    h = raw.strip()
    h = re.sub(r"^(https?://)?(www\.)?github\.com/", "", h).strip("/ ")
    h = h.lstrip("@")
    if not HANDLE_RE.match(h):
        sys.exit(f"'{raw}' doesn't look like a GitHub handle.")
    return h


def get_handle(arg):
    if arg:
        return clean_handle(arg)
    if not sys.stdin.isatty():
        print("needs input: the candidate's GitHub handle (not on the CV or invite; ask Ivana or the recruiter)",
              file=sys.stderr)
        sys.exit(2)
    return clean_handle(input("Candidate's GitHub handle: "))


def confirm(question, yes):
    if yes:
        return True
    if not sys.stdin.isatty():
        sys.exit(f"Not confirmed: {question} (run with --yes, or on a terminal)")
    return input(f"{question} [y/N] ").strip().lower() == "y"


def repo_exists(repo):
    return gh("api", f"repos/{ORG}/{repo}", check=False)[0] == 0


def list_access():
    """Print each API-Exercise-* fork with its outside collaborators and pending invitations."""
    _, out, _ = gh("api", f"orgs/{ORG}/repos", "--paginate", "--jq", ".[].name")
    repos = sorted(n for n in out.split() if n.startswith(SOURCE + "-"))
    if not repos:
        print("No candidate forks.")
    for repo in repos:
        _, out, _ = gh("api", f"repos/{ORG}/{repo}/collaborators?affiliation=outside", "--paginate",
                       "--jq", ".[].login")
        people = out.split()
        _, out, _ = gh("api", f"repos/{ORG}/{repo}/invitations", "--paginate", "--jq", ".[].invitee.login")
        pending = out.split()
        state = ", ".join(people + [f"{p} (invited)" for p in pending]) or "no outside access"
        print(f"{repo}: {state}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("handle", nargs="?", help="candidate's GitHub handle")
    ap.add_argument("--remove", action="store_true", help="remove their access after the session")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
    ap.add_argument("--list", action="store_true", help="show the candidate forks and who has access")
    ap.add_argument("--yes", "-y", action="store_true", help="don't ask before changing anything")
    args = ap.parse_args()

    if args.list:
        return list_access()

    handle = get_handle(args.handle)
    repo = f"{SOURCE}-{handle}"
    full = f"{ORG}/{repo}"
    dry = args.dry_run

    rc, out, _ = gh("api", f"users/{handle}", check=False)
    if rc:
        sys.exit(f"No GitHub user '{handle}'. Check the spelling with the candidate.")
    print(f"GitHub user {handle}: {json.loads(out).get('name') or '(no display name)'}")

    exists = repo_exists(repo)

    if args.remove:
        if not exists:
            sys.exit(f"{full} doesn't exist, so there is no access to remove.")
        if not confirm(f"Remove {handle}'s access to {full}?", args.yes or dry):
            sys.exit("Left as it was.")
        _, out, _ = gh("api", f"repos/{full}/invitations", "--paginate")
        invites = [i for i in json.loads(out or "[]") if i["invitee"]["login"].lower() == handle.lower()]
        for i in invites:
            print(f"{'Would cancel' if dry else 'Cancelling'} pending invitation {i['id']}")
            if not dry:
                gh("api", "-X", "DELETE", f"repos/{full}/invitations/{i['id']}")
        rc, _, _ = gh("api", f"repos/{full}/collaborators/{handle}", check=False)
        if rc == 0:
            print(f"{'Would remove' if dry else 'Removing'} {handle} as a collaborator on {full}")
            if not dry:
                gh("api", "-X", "DELETE", f"repos/{full}/collaborators/{handle}")
        elif not invites:
            print(f"{handle} had no access to {full} (already removed).")
        print(f"Done. https://github.com/{full}/settings/access")
        return

    if exists:
        print(f"{full} already exists; reusing it.")
    else:
        if not confirm(f"Fork {ORG}/{SOURCE} as {full} and give {handle} write access?", args.yes or dry):
            sys.exit("Nothing changed.")
        if dry:
            print(f"Would fork {ORG}/{SOURCE} to {full}")
        else:
            gh("repo", "fork", f"{ORG}/{SOURCE}", "--org", ORG, "--fork-name", repo, "--clone=false")
            for _ in range(15):  # forks are made in the background
                if repo_exists(repo):
                    break
                time.sleep(2)
            else:
                sys.exit(f"Forked, but {full} isn't visible yet. Run this again in a minute.")
            print(f"Forked to {full}")

    rc, _, _ = gh("api", f"repos/{full}/collaborators/{handle}", check=False) if exists else (1, "", "")
    if rc == 0:
        print(f"{handle} already has access.")
    elif dry:
        print(f"Would give {handle} write access to {full}")
    else:
        gh("api", "-X", "PUT", f"repos/{full}/collaborators/{handle}", "-f", "permission=push")
        print(f"Invited {handle} with write access (they must accept the invitation from GitHub).")
    print(f"Repo:   https://github.com/{full}")
    print(f"Access: https://github.com/{full}/settings/access")
    print(f"Afterwards: interview-fork.py {handle} --remove")


if __name__ == "__main__":
    main()
