#!/usr/bin/env python3
"""
Squash consecutive 'automate: tick ...' commits into single commits.

Strategy: let git generate the rebase todo (with --rebase-merges so merge
commits are handled correctly), then intercept it via GIT_SEQUENCE_EDITOR
to convert consecutive automate picks into reword+fixup sequences.

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
import json
from itertools import groupby


def run(cmd, **kwargs):
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print(f"Error running {cmd}:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def get_commits(since=None):
    """Return list of (hash, subject, is_merge) from oldest to newest."""
    rev_range = f"{since}..HEAD" if since else "HEAD"
    # %P = parent hashes (space-separated; merge commits have 2+)
    out = run(["git", "log", "--format=%H\t%P\t%s", "--reverse", rev_range])
    if not out:
        return []
    commits = []
    for line in out.splitlines():
        parts = line.split("\t", 2)
        h = parts[0]
        parents = parts[1].split() if len(parts) > 1 else []
        s = parts[2] if len(parts) > 2 else ""
        commits.append((h, s, len(parents) > 1))
    return commits


def is_automate(subject):
    return subject.startswith("automate:")


def build_groups(commits):
    """
    Group commits into consecutive runs of automate vs non-automate.
    Returns list of ("automate"|"normal", [(hash, subject, is_merge), ...])
    """
    groups = []
    for key, items in groupby(commits, key=lambda c: is_automate(c[1])):
        groups.append(("automate" if key else "normal", list(items)))
    return groups


def make_combined_msg(commits):
    timestamps = []
    for _, subject, _ in commits:
        m = re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', subject)
        if m:
            timestamps.append(m.group())
    if timestamps:
        return f"automate: tick {timestamps[0]} ~ {timestamps[-1]} ({len(commits)} ticks)"
    return f"automate: {len(commits)} ticks squashed"


def preview(groups):
    automate_groups = [(k, cs) for k, cs in groups if k == "automate" and len(cs) > 1]
    if not automate_groups:
        print("No consecutive automate commits to squash.")
        return False
    print(f"Found {len(automate_groups)} group(s) of consecutive automate commits to squash:\n")
    for _, cs in automate_groups:
        msg = make_combined_msg(cs)
        print(f"  {len(cs)} commits  {cs[0][0][:7]}..{cs[-1][0][:7]}  →  \"{msg}\"")
    return True


def modify_todo(todo_path, squash_map, reword_map):
    """
    Read git-generated todo, replace consecutive automate pick lines with
    reword (first) + fixup (rest). squash_map: hash -> new message.
    reword_map: hash -> new message (same as squash_map for first of each group).
    """
    with open(todo_path) as f:
        lines = f.readlines()

    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Only touch "pick <hash> automate: ..." lines
        m = re.match(r'^(pick)\s+([0-9a-f]+)\s+(automate:.*)$', stripped)
        if m and m.group(2) in reword_map:
            h = m.group(2)
            new_msg = reword_map[h]
            out.append(f"reword {h} {new_msg}\n")
        elif re.match(r'^(pick)\s+([0-9a-f]+)\s+(automate:.*)$', stripped):
            h = re.match(r'^pick\s+([0-9a-f]+)', stripped).group(1)
            if h in squash_map:
                out.append(f"fixup {h} {stripped.split(None, 2)[2] if len(stripped.split(None, 2)) > 2 else ''}\n")
            else:
                out.append(line)
        else:
            out.append(line)
        i += 1

    with open(todo_path, "w") as f:
        f.writelines(out)


def main():
    dry_run = "--dry-run" in sys.argv
    since = None
    if "--since" in sys.argv:
        idx = sys.argv.index("--since")
        since = sys.argv[idx + 1]

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

    if not preview(groups):
        return

    if dry_run:
        print("\n[dry-run] No changes made.")
        return

    print()
    answer = input("Proceed with rebase? This rewrites history. [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        return

    # Build lookup maps for the sequence editor
    # reword_map: first hash of each automate group -> combined message
    # fixup_set: hashes of non-first commits in each automate group
    reword_map = {}
    fixup_set = set()
    for kind, cs in groups:
        if kind == "automate" and len(cs) > 1:
            msg = make_combined_msg(cs)
            reword_map[cs[0][0]] = msg
            for h, _, _ in cs[1:]:
                fixup_set.add(h)

    # Write a GIT_SEQUENCE_EDITOR script that modifies the todo in-place
    seq_editor = tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="squash_seq_"
    )
    seq_editor.write("#!/usr/bin/env python3\n")
    seq_editor.write(f"reword_map = {json.dumps(reword_map)}\n")
    seq_editor.write(f"fixup_set = {json.dumps(list(fixup_set))}\n")
    seq_editor.write(r"""
import sys, re

todo_path = sys.argv[1]
with open(todo_path) as f:
    lines = f.readlines()

out = []
for line in lines:
    stripped = line.strip()
    m = re.match(r'^pick\s+([0-9a-f]+)\s+(automate:.*)', stripped)
    if m:
        h, subj = m.group(1), m.group(2)
        # Match by prefix (git todo may use abbreviated hashes)
        matched_reword = next((k for k in reword_map if k.startswith(h) or h.startswith(k)), None)
        matched_fixup = next((k for k in fixup_set if k.startswith(h) or h.startswith(k)), None)
        if matched_reword:
            out.append(f"reword {h} {reword_map[matched_reword]}\n")
            continue
        if matched_fixup:
            out.append(f"fixup {h} {subj}\n")
            continue
    out.append(line)

with open(todo_path, "w") as f:
    f.writelines(out)
""")
    seq_editor.close()
    os.chmod(seq_editor.name, 0o755)

    # Write a GIT_EDITOR script that accepts reword commit messages as-is
    # (the message is already set correctly in the reword line subject,
    #  but git still opens an editor for reword — we just write back whatever)
    msg_editor = tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False, prefix="squash_msg_"
    )
    msg_editor.write("#!/bin/sh\n# Accept the commit message as-is\nexit 0\n")
    msg_editor.close()
    os.chmod(msg_editor.name, 0o755)

    oldest_hash = commits[0][0]
    parent_result = subprocess.run(
        ["git", "rev-parse", f"{oldest_hash}^"],
        capture_output=True, text=True
    )
    use_root = parent_result.returncode != 0

    rebase_cmd = ["git", "rebase", "-i", "--rebase-merges"]
    if use_root:
        rebase_cmd.append("--root")
    else:
        rebase_cmd.append(parent_result.stdout.strip())

    env = os.environ.copy()
    env["GIT_SEQUENCE_EDITOR"] = seq_editor.name
    env["GIT_EDITOR"] = msg_editor.name

    print(f"\nRunning: {' '.join(rebase_cmd)}")
    try:
        result = subprocess.run(rebase_cmd, env=env)
        if result.returncode != 0:
            print("\nRebase failed. Run 'git rebase --abort' to recover.")
            sys.exit(1)
        print("\nDone! Consecutive automate commits have been squashed.")
        print("Force-push to update the remote:")
        print("  git push --force-with-lease")
    finally:
        for p in [seq_editor.name, msg_editor.name]:
            try:
                os.unlink(p)
            except Exception:
                pass


if __name__ == "__main__":
    main()
