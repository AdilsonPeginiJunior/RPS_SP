import subprocess
import sys


def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def main():
    if run('git rev-parse --is-inside-work-tree').returncode != 0:
        return 0

    run('git fetch --all --prune')

    upstream = run('git rev-parse --abbrev-ref --symbolic-full-name @{u}')
    if upstream.returncode != 0:
        return 0

    rev_list = run('git rev-list --count --left-right @{u}...HEAD')
    if rev_list.returncode != 0:
        return 0

    counts = rev_list.stdout.strip().split()
    if len(counts) != 2:
        return 0

    behind, ahead = counts
    if ahead != '0':
        push = run('git push')
        sys.stdout.write(push.stdout)
        sys.stderr.write(push.stderr)
        return push.returncode

    return 0


if __name__ == '__main__':
    sys.exit(main())
