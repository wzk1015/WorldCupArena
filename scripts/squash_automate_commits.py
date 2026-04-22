#!/usr/bin/env python3
"""
Squash consecutive 'automate: tick ...' commits into single commits.

Usage:
    python3 scripts/squash_automate_commits.py [--dry-run] [--since <ref>]

Options:
    --dry-run   Show what would be squashed without modifying history
    --since     Only consider commits reachable from this ref (default: all)
"""

import subprocess
import sys
import os
import tempfile
import re
from itertools import groupby


def run(cmd, **kwargs):
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print(f"Error running {cmd}:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def get_commits(since=None):
    """Return list of (hash, subject) from oldest to newest."""
    rev_range = f"{since}..HEAD" if since else "HEAD"
    out = run(["git", "log", "--format=%H %s", "--reverse", rev_range])
    if not out:
        return []
    commits = []
    for line in out.splitlines():
        parts = line.split(" ", 1)
        commits.append((parts[0], parts[1] if len(parts) > 1 else ""))
    return commits


def is_automate(subject):
    return subject.startswith("automate:")


def build_groups(commits):
    """
    Return list of groups. Each group is either:
      - ("automate", [list of (hash, subject)])   — consecutive automate commits
      - ("normal",   [(hash, subject)])            — a single non-automate commit
    """
    groups = []
    for key, items in groupby(commits, key=lambda c: is_automate(c[1])):
        item_list = list(items)
        groups.append(("automate" if key else "normal", item_list))
    return groups


def squash_group(commits):
    """
    Squash a list of commits (oldest first) by:
      - soft-resetting to the parent of the first commit
      - making a new commit with a combined message
    Uses git rebase with a generated todo.
    """
    first_hash = commits[0][0]
    last_hash = commits[-1][0]

    # Get timestamps from subjects for the combined message
    timestamps = []
    for _, subject in commits:
        m = re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', subject)
        if m:
            timestamps.append(m.group())

    if timestamps:
        combined_msg = f"automate: tick {timestamps[0]} ~ {timestamps[-1]} ({len(commits)} ticks)"
    else:
        combined_msg = f"automate: {len(commits)} ticks squashed"

    return first_hash, last_hash, combined_msg


def write_rebase_todo(groups, todo_path):
    """Write git-rebase-todo file."""
    with open(todo_path, "w") as f:
        for kind, commits in groups:
            if kind == "normal" or len(commits) == 1:
                for h, s in commits:
                    f.write(f"pick {h} {s}\n")
            else:
                # First commit: pick; rest: squash
                first = True
                for h, s in commits:
                    action = "pick" if first else "squash"
                    f.write(f"{action} {h} {s}\n")
                    first = False


def get_rebase_root(commits):
    """Return the parent of the oldest commit, or --root if it's the first commit."""
    oldest = commits[0][0]
    result = subprocess.run(
        ["git", "rev-parse", f"{oldest}^"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None  # root commit
    return result.stdout.strip()


def main():
    dry_run = "--dry-run" in sys.argv
    since = None
    if "--since" in sys.argv:
        idx = sys.argv.index("--since")
        since = sys.argv[idx + 1]

    # Ensure working tree is clean (skip check for dry-run)
    if not dry_run:
        status = run(["git", "status", "--porcelain"])
        if status:
            print("Working tree is not clean. Please commit or stash changes first.")
            sys.exit(1)

    commits = get_commits(since)
    if not commits:
        print("No commits found.")
        return

    groups = build_groups(commits)

    # Summarize what will be squashed
    automate_groups = [(kind, cs) for kind, cs in groups if kind == "automate" and len(cs) > 1]
    if not automate_groups:
        print("No consecutive automate commits to squash.")
        return

    print(f"Found {len(automate_groups)} group(s) of consecutive automate commits to squash:\n")
    for kind, cs in automate_groups:
        first_hash, last_hash, combined_msg = squash_group(cs)
        print(f"  {len(cs)} commits  {first_hash[:7]}..{last_hash[:7]}  →  \"{combined_msg}\"")

    if dry_run:
        print("\n[dry-run] No changes made.")
        return

    print()
    answer = input("Proceed with interactive rebase? This rewrites history. [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        return

    # Build the rebase todo file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tf:
        todo_path = tf.name

    try:
        write_rebase_todo(groups, todo_path)

        # Use GIT_SEQUENCE_EDITOR to feed our pre-built todo
        editor_script = tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        )
        editor_script.write(f"#!/bin/sh\ncp '{todo_path}' \"$1\"\n")
        editor_script.close()
        os.chmod(editor_script.name, 0o755)

        # Also need GIT_EDITOR for commit message merging (use default: just accept)
        msg_editor = tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        )

        # For each squash group, build the expected combined message
        # We'll handle message editing via a custom GIT_EDITOR that rewrites the file
        squash_messages = {}
        for kind, cs in groups:
            if kind == "automate" and len(cs) > 1:
                _, _, combined_msg = squash_group(cs)
                # Key by the set of hashes in the group
                squash_messages[frozenset(h for h, _ in cs)] = combined_msg

        # Since squash message editing is complex, use a helper that just picks
        # the first line (already the combined subject we want after reword).
        # Instead, use "fixup" for all but first, which discards subsequent messages.
        # Rewrite todo to use fixup instead of squash, then reword the first.
        with open(todo_path, "w") as f:
            for kind, commits_in_group in groups:
                if kind == "normal" or len(commits_in_group) == 1:
                    for h, s in commits_in_group:
                        f.write(f"pick {h} {s}\n")
                else:
                    _, _, combined_msg = squash_group(commits_in_group)
                    # reword first, fixup the rest
                    first = True
                    for h, s in commits_in_group:
                        if first:
                            f.write(f"reword {h} {s}\n")
                            first = False
                        else:
                            f.write(f"fixup {h} {s}\n")
                    # store combined message keyed by first hash
                    squash_messages[commits_in_group[0][0]] = combined_msg

        # GIT_EDITOR script: if the file looks like a commit message for one of our
        # reworded commits, replace it with the combined message.
        msg_editor_path = msg_editor.name
        msg_editor.write("#!/usr/bin/env python3\n")
        msg_editor.write("import sys, re\n")
        msg_editor.write(f"messages = {dict((k, v) for k, v in squash_messages.items() if isinstance(k, str))!r}\n")
        msg_editor.write("""
path = sys.argv[1]
with open(path) as f:
    content = f.read()
lines = [l for l in content.splitlines() if not l.startswith('#')]
subject = lines[0].strip() if lines else ''
# Check if this commit subject matches a reword target
for orig_subject, new_msg in messages.items():
    if orig_subject in subject or subject in orig_subject:
        with open(path, 'w') as f:
            f.write(new_msg + '\\n')
        sys.exit(0)
# Otherwise keep as-is (write back first line only for cleanliness)
with open(path, 'w') as f:
    f.write(subject + '\\n')
""")
        msg_editor.close()
        os.chmod(msg_editor_path, 0o755)

        root_parent = get_rebase_root(commits)
        rebase_base = root_parent if root_parent else "--root"

        env = os.environ.copy()
        env["GIT_SEQUENCE_EDITOR"] = editor_script.name
        env["GIT_EDITOR"] = msg_editor_path

        rebase_cmd = ["git", "rebase", "-i"]
        if rebase_base == "--root":
            rebase_cmd.append("--root")
        else:
            rebase_cmd.append(rebase_base)

        print(f"\nRunning: {' '.join(rebase_cmd)}")
        result = subprocess.run(rebase_cmd, env=env)
        if result.returncode != 0:
            print("\nRebase failed. You may need to run 'git rebase --abort' to recover.")
            sys.exit(1)

        print("\nDone! Consecutive automate commits have been squashed.")
        print("If you have a remote, you will need to force-push:")
        print("  git push --force-with-lease")

    finally:
        for p in [todo_path, editor_script.name, msg_editor_path]:
            try:
                os.unlink(p)
            except Exception:
                pass


if __name__ == "__main__":
    main()
