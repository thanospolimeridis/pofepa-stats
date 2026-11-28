#!/usr/bin/env python3
"""Cut a release of the site: a new VERSION, its CHANGELOG section, one commit and its tag.

    python3 scripts/release.py          show the current version and what is waiting
    python3 scripts/release.py patch    fixes and data refreshes            1.4.2 -> 1.4.3
    python3 scripts/release.py minor    new features, newly covered data    1.4.2 -> 1.5.0
    python3 scripts/release.py major    redesigns, links that stop working  1.4.2 -> 2.0.0
    python3 scripts/release.py 1.0.0    a version named outright

The changelog section lists the subject of every commit since the release before.
--summary "One line" (repeatable) lists the given lines instead.

Nothing is pushed: publishing stays the separate, deliberate step printed at the end.
"""
import argparse
import datetime as dt
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import ROOT, VERSION_FORMAT, read_version  # noqa: E402

BRANCH = 'develop'
PARTS = ('major', 'minor', 'patch')
CHANGELOG_HEAD = '''# Changelog

What each public release of the site changed, newest first. `scripts/release.py`
adds a section when a release is cut, one line per commit since the release
before it. See "Releases and versions" in the README.
'''


class ReleaseError(Exception):
    pass


def git(root, *args, check=True):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True)
    if check and result.returncode:
        raise ReleaseError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip() if result.returncode == 0 else ''


def number(version):
    return tuple(int(part) for part in version.split('.'))


def bump(version, part):
    major, minor, patch = number(version)
    return {'major': f'{major+1}.0.0', 'minor': f'{major}.{minor+1}.0', 'patch': f'{major}.{minor}.{patch+1}'}[part]


def released(root):
    """Every version that already has a release tag, in ascending order."""
    names = git(root, 'tag', '--list', 'v*').split()
    return sorted((name[1:] for name in names if VERSION_FORMAT.fullmatch(name[1:])), key=number)


def waiting(root, previous):
    """Subjects of the commits a release would carry, oldest first."""
    span = [f'v{previous}..HEAD'] if previous else ['HEAD']
    return [line for line in git(root, 'log', '--no-merges', '--reverse', '--format=%s', *span).splitlines() if line]


def with_section(changelog, version, day, lines):
    """The changelog with the new release placed above the earlier ones."""
    section = f'## {version} — {day}\n\n' + ''.join(f'- {line}\n' for line in lines)
    head, mark, rest = (changelog or CHANGELOG_HEAD).partition('\n## ')
    return head.rstrip('\n') + '\n\n' + section + (mark + rest if mark else '')


def check_ready(root):
    """Refuse a release that could not be published as it stands."""
    branch = git(root, 'branch', '--show-current')
    if branch != BRANCH:
        raise ReleaseError(f'Releases are cut on {BRANCH}; this checkout is on {branch or "a detached commit"}.')
    # Untracked files (an editor's or an agent's local folder) never enter the release commit.
    if git(root, 'status', '--porcelain', '--untracked-files=no'):
        raise ReleaseError('The working tree has uncommitted changes; commit or remove them first.')
    online = 'origin' in git(root, 'remote').split()
    for name in (BRANCH, 'main'):
        if online:
            # Best effort: offline, the last known state of the remote branch is compared instead.
            subprocess.run(['git', 'fetch', '--quiet', 'origin', name], cwd=root, capture_output=True)
        remote = git(root, 'rev-parse', '-q', '--verify', f'refs/remotes/origin/{name}', check=False)
        if remote and subprocess.run(['git', 'merge-base', '--is-ancestor', remote, 'HEAD'], cwd=root).returncode:
            raise ReleaseError(f'origin/{name} has commits this checkout lacks; merge them in before releasing.')


def cut(root, target, today=None, summary=None):
    """Write the release at HEAD and return its version; nothing leaves the clone.

    The changelog lists one line per commit since the previous release, or the
    lines in summary when a release is better described by hand.
    """
    check_ready(root)
    current, tags = read_version(root), released(root)
    previous = tags[-1] if tags else None
    if target in PARTS:
        if current is None:
            raise ReleaseError('There is no VERSION file to count from; name the first version outright.')
        if current not in tags:
            raise ReleaseError(f'{current} is in VERSION but was never released; release it first: '
                               f'python3 scripts/release.py {current}')
        version = bump(current, target)
    elif VERSION_FORMAT.fullmatch(target):
        version = target
    else:
        raise ReleaseError(f'Expected major, minor, patch or a version such as 1.4.2, not {target!r}.')
    if previous and number(version) <= number(previous):
        raise ReleaseError(f'{version} does not come after the last release, {previous}.')
    lines = waiting(root, previous) if previous else ['First versioned release.']
    if not lines:
        raise ReleaseError(f'Nothing has been committed since {previous}; there is nothing to release.')
    if summary:
        lines = [' '.join(line.split()) for line in summary]
        if not all(lines):
            raise ReleaseError('A --summary line is empty.')
    day = (today or dt.date.today()).isoformat()
    changelog = root/'CHANGELOG.md'
    existing = changelog.read_text(encoding='utf-8') if changelog.exists() else ''
    changelog.write_text(with_section(existing, version, day, lines), encoding='utf-8')
    (root/'VERSION').write_text(version+'\n', encoding='utf-8')
    git(root, 'add', 'VERSION', 'CHANGELOG.md')
    git(root, 'commit', '--quiet', '-m', f'Release {version}')
    git(root, 'tag', '--annotate', f'v{version}', '-m', f'Release {version}')
    return version


def guard_installed(root):
    """Whether this clone runs the tracked pre-push guard (hooks are not cloned)."""
    installed = (root/git(root, 'rev-parse', '--git-common-dir')/'hooks'/'pre-push')
    tracked = root/'scripts'/'hooks'/'pre-push'
    return installed.exists() and tracked.exists() and installed.read_bytes() == tracked.read_bytes()


def status(root):
    current, tags = read_version(root), released(root)
    previous = tags[-1] if tags else None
    lines = waiting(root, previous) if previous else []
    print('VERSION:', current or 'none')
    print('Last release:', f'v{previous}' if previous else 'none yet')
    if previous is None:
        print(f'Cut the first one with: python3 scripts/release.py {current or "1.0.0"}')
    elif lines:
        print(f'{len(lines)} commit(s) since v{previous}:')
        for line in lines:
            print('  -', line)
    else:
        print('Nothing is waiting to be released.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('target', nargs='?', help='major, minor, patch, or an explicit version; omit to see what is waiting')
    parser.add_argument('--summary', action='append', metavar='TEXT',
                        help='a changelog line to list instead of one per commit; repeat for more lines')
    args = parser.parse_args()
    try:
        if args.target is None:
            if args.summary:
                raise ReleaseError('--summary describes a release; name the version or part to cut.')
            status(ROOT)
            return
        version = cut(ROOT, args.target, summary=args.summary)
    except ReleaseError as error:
        raise SystemExit(f'Not released: {error}')
    print(f'Release {version} is committed and tagged v{version} on {BRANCH}. Nothing has been pushed.')
    print('Publish it, when the release is wanted, with:')
    print(f'    PUBLISH=1 git push --atomic origin {BRANCH} {BRANCH}:main v{version}')
    if not guard_installed(ROOT):
        print('This clone does not have the current publish guard. Install it with:')
        print('    cp scripts/hooks/pre-push "$(git rev-parse --git-common-dir)/hooks/pre-push"')


if __name__ == '__main__':
    main()
