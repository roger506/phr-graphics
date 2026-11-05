# community-specs

Render specs for the Community Update System. A push to this folder triggers
`.github/workflows/render-community.yml`, which renders every `*.json` here and
renames it to `*.json.done` when it has committed the assets.

Two rules, both learned expensively:

1. **One spec at a time.** Three pending specs exceed the 45-minute job cap and
   the repo deadlocks.
2. **No pushes of ANY kind to this repo while a render is running.** The runner
   checks out `main`, renders for about sixteen minutes, then pushes the assets
   back. Any commit that lands in that window makes its push fail and the
   finished renders are discarded, leaving the spec pending. On 2026-11-05 five
   pushes to `blog-bodies/` during the window cost one complete Riverstone
   render. The path filter does not protect you: it decides what STARTS a run,
   not what breaks one.

This file exists so a run can be re-triggered without touching a spec.
