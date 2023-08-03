# SmallAction

some small actions

1. trending
    1. I added Token while still got
    ''' c++
        Run ad-m/github-push-action@master
  with:
    github_token: ***
    branch: example_action
    github_url: https://github.com
    directory: .
  env:
    pythonLocation: /opt/hostedtoolcache/Python/3.8.17/x64
    LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.8.17/x64/lib
Push to branch example_action
remote: Write access to repository not granted.
fatal: unable to access 'https://github.com/introverti/SmallAction.git/': The requested URL returned error: 403
Error: Invalid exit code: 128
    at ChildProcess.<anonymous> (/home/runner/work/_actions/ad-m/github-push-action/master/start.js:30:21)
    at ChildProcess.emit (node:events:527:28)
    at maybeClose (node:internal/child_process:1092:16)
    at Process.ChildProcess._handle.onexit (node:internal/child_process:302:5) {
  code: 128
}
