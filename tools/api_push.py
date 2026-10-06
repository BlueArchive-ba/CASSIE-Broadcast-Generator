"""通过 GitHub API 推送当前提交（网络受限时的替代通道）。

用途：这台机器直连 github.com:443 会超时（DNS 解析到 20.205.243.166），
`git push` 因此失败；而 gh 的 api.github.com 通道是通的。
这个脚本把 Git Data API 当传输层用，效果等价于一次 push。

用法：
    python tools/api_push.py            # 推送当前 HEAD
    python tools/api_push.py --dry-run  # 只看会改哪些文件

限制：GitHub 会规范化提交的 author/committer 时间戳，因此推送后
远端提交的 sha 与本地不同。内容（树）完全一致，用
`git fetch && git reset --hard origin/main` 可在网络恢复后统一。
"""
import argparse
import base64
import json
import os
import subprocess
import sys

REPO = 'BlueArchive-ba/CASSIE-Broadcast-Generator'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANCH = 'main'


def git(*args, binary=False):
    result = subprocess.run(['git'] + list(args), cwd=ROOT, capture_output=True)
    if result.returncode != 0:
        raise SystemExit('git {} 失败: {}'.format(
            ' '.join(args), result.stderr.decode('utf-8', 'ignore')[:300]))
    return result.stdout if binary else result.stdout.decode('utf-8', 'ignore').strip()


def api(path, method='GET', payload=None):
    args = ['gh', 'api', '--method', method, path]
    if payload is not None:
        result = subprocess.run(args + ['--input', '-'],
                                input=json.dumps(payload).encode('utf-8'),
                                capture_output=True)
    else:
        result = subprocess.run(args, capture_output=True)
    if result.returncode != 0:
        raise SystemExit('gh api {} 失败: {}'.format(
            path, result.stderr.decode('utf-8', 'ignore')[:300]))
    return json.loads(result.stdout.decode('utf-8'))


def local_files():
    """本地被跟踪的文件 -> (sha, mode)。不能带 -t，tree 不能当 blob 传。"""
    files = {}
    for line in git('ls-tree', '-r', 'HEAD').split('\n'):
        if not line.strip():
            continue
        meta, path = line.split('\t', 1)
        mode, _otype, sha = meta.split()
        files[path] = (sha, str(mode).zfill(6))
    return files


def remote_files(tree_sha):
    """远端树里的文件 -> (sha, mode)，只取 blob。"""
    out = api('repos/{}/git/trees/{}?recursive=1'.format(REPO, tree_sha))
    return {i['path']: (i['sha'], str(i['mode']).zfill(6))
            for i in out.get('tree', []) if i['type'] == 'blob'}


def upload_blob(sha):
    raw = git('cat-file', '-p', sha, binary=True)
    created = api('repos/{}/git/blobs'.format(REPO), 'POST',
                  {'content': base64.b64encode(raw).decode('ascii'),
                   'encoding': 'base64'})
    if created['sha'] != sha:
        raise SystemExit('blob {} 上传后 sha 不一致（{}）'.format(
            sha[:8], created['sha'][:8]))
    return created['sha']


def build_tree(prefix, local, remote):
    children = {}
    for path, value in local.items():
        if prefix:
            if not path.startswith(prefix + '/'):
                continue
            rest = path[len(prefix) + 1:]
        else:
            rest = path
        if '/' in rest:
            children.setdefault(rest.split('/', 1)[0], None)
        else:
            children[rest] = value

    entries = []
    for name in sorted(children):
        value = children[name]
        if value is None:
            sub = (prefix + '/' + name) if prefix else name
            entries.append({'path': name, 'mode': '040000', 'type': 'tree',
                            'sha': build_tree(sub, local, remote)})
            continue
        sha, mode = value
        local_path = (prefix + '/' + name) if prefix else name
        known = remote.get(local_path)
        blob_sha = sha if (known and known[0] == sha) else upload_blob(sha)
        entries.append({'path': name, 'mode': mode, 'type': 'blob',
                        'sha': blob_sha})
    return api('repos/{}/git/trees'.format(REPO), 'POST',
               {'tree': entries})['sha']


def main():
    parser = argparse.ArgumentParser(description='通过 GitHub API 推送')
    parser.add_argument('--dry-run', action='store_true', help='只显示改动')
    parser.add_argument('--message', help='覆盖提交信息')
    opts = parser.parse_args()

    remote_head = api('repos/{}/git/ref/heads/{}'.format(REPO, BRANCH))['object']['sha']
    local_head = git('rev-parse', 'HEAD')
    base_tree = api('repos/{}/git/commits/{}'.format(REPO, remote_head))['tree']['sha']

    print('  远端 HEAD: {}  树 {}'.format(remote_head[:8], base_tree[:12]))
    print('  本地 HEAD: {}'.format(local_head[:8]))

    local = local_files()
    remote = remote_files(base_tree)
    changed = sorted(p for p in local if remote.get(p, (None,))[0] != local[p][0])
    removed = sorted(p for p in remote if p not in local)
    print('  本地 {} 个文件，远端 {} 个'.format(len(local), len(remote)))
    print('  改动 {} 个，删除 {} 个'.format(len(changed), len(removed)))
    for path in changed[:20]:
        print('    M {}'.format(path))
    for path in removed[:20]:
        print('    D {}'.format(path))

    if not changed and not removed:
        print('  内容已一致，无需推送')
        return

    if opts.dry_run:
        print('  （--dry-run，未推送）')
        return

    tree_sha = build_tree('', local, remote)
    message = opts.message or git('log', '-1', '--pretty=%B', local_head)
    commit = api('repos/{}/git/commits'.format(REPO), 'POST',
                 {'message': message, 'tree': tree_sha, 'parents': [remote_head]})
    api('repos/{}/git/refs/heads/{}'.format(REPO, BRANCH), 'PATCH',
        {'sha': commit['sha'], 'force': False})
    print()
    print('  已推送: {} -> {}'.format(remote_head[:8], commit['sha'][:8]))
    print('  远端树: {}'.format(tree_sha[:12]))
    print('  注意：远端 sha 与本地不同（GitHub 规范化了时间戳），内容一致。')


if __name__ == '__main__':
    main()
