# Private Repository TODO

> Scope: private repository `lbx154/argus-skill` after synchronizing its `main`
> branch to public `lbx154/Argus:main` on 2026-08-06.
>
> Public `main` is authoritative. Do not merge the old private history wholesale.

## P0 — Keep the synchronized baseline operational

- [ ] Controlled-restart the long-running private Web service currently bound to
      `127.0.0.1:8799`; it was started before the repository synchronization and
      still holds the previous Python code in memory.
- [ ] Validate a clean private installation from synchronized `main`: create a new
      venv, install the package using the public instructions, run the public smoke
      tests, and verify CLI/Web startup.
- [ ] Validate the preserved local untracked `config/` against the synchronized
      public configuration schema. Keep credentials and machine-local settings out
      of Git.
- [ ] Record the synchronized baseline in operations documentation:
      `main = 7db07ce1259d51391e0df2b79f00a1706ea255d8`.

## P0 — Protect history and future synchronization

- [ ] Treat private branch `202686` as an immutable backup of the former private
      `main` at `f3439e8c2afdaa5e0f0ce6155edfdb47a6f3d300`.
- [ ] Protect `202686` from force-push/deletion in GitHub branch rules.
- [ ] Require private changes to use topic branches and PRs; private `main` should
      not drift from public `main` unless an explicit private-overlay policy is
      approved.
- [ ] Automate public-to-private synchronization with three checks: fetch public,
      back up the observed private head, then update private `main` using
      `--force-with-lease` and verify equal tree hashes.

## P1 — Classify the former private-only tree

The `202686` backup differs from synchronized `main` in 535 paths:

- 532 paths exist only in the former private tree;
- 2 paths are modified (`README.md`, `README.zh-CN.md`);
- 1 path exists only in public (`docs/assets/argus-wechat-group.jpg`).

Do not restore these paths in bulk. Produce a manifest assigning every path one of:

1. `archive-private` — retain only on `202686` or external private storage;
2. `private-overlay` — restore on a reviewed private topic branch;
3. `candidate-public` — propose upstream to the public repository via PR;
4. `obsolete` — intentionally retire.

### Review groups

- [ ] **Technical report sources and evidence (215 paths):** decide whether LaTeX,
      editable figures, evidence bundles, and PPT sources should be public,
      private-overlay, or immutable release artifacts. The public PDF remains the
      authority until that policy is decided.
- [ ] **GitHub/Impeccable automation (105 `.github` paths plus `.agents` and
      `.impeccable`):** audit third-party hooks, generated assets, permissions, and
      maintenance burden before restoring anything.
- [ ] **Frontend/demo material (66 paths):** separate source from generated `dist/`,
      remove duplicated math-vertical demo bundles, and restore only reproducible
      artifacts required by a private deployment.
- [ ] **Private documentation (61 paths):** reconcile architecture/design/runtime
      docs against public current behavior. Do not restore stale documents merely
      because they existed in the old repository.
- [ ] **Release and experiment scripts (35 paths):** review binary/npm release
      tooling, MLE-Bench campaign scripts, and verification helpers for secrets,
      obsolete interfaces, and reproducibility before selecting any overlay.
- [ ] **Tests (16 paths):** restore tests only with the production surface they
      validate; avoid private tests for code no longer present on public `main`.
- [ ] **Packaging/deployment:** review `packaging/`, the systemd unit, binary build
      definitions, and npm launchers as one coherent private deployment feature.
- [ ] **Large/private assets:** keep presentations, DOCX/PDF working files, research
      state, and internal evidence off synchronized `main` unless publication and
      licensing are explicit.

## P1 — Verify that no functionality was silently lost

- [ ] Compare public smoke behavior with the former private release on `202686` for
      CLI startup, Manager routing, bounded DAG dispatch, four-role execution,
      Web/TUI startup, and persistent session recovery.
- [ ] For every behavioral difference, create a small reproducible issue before
      proposing code restoration. A file diff alone is not evidence of regression.
- [ ] Prefer public implementations when both trees provide the same capability;
      restore only private behavior that has a current owner and a testable need.

## P2 — Repository hygiene

- [ ] Remove stale local build/cache directories from operational checkouts without
      touching `config/` or the `202686` backup.
- [ ] Keep generated frontend bundles and release manifests reproducible from source;
      do not hand-edit generated outputs.
- [ ] Periodically verify:

  ```bash
  git ls-remote https://github.com/lbx154/Argus refs/heads/main
  git ls-remote https://github.com/lbx154/argus-skill refs/heads/main
  git rev-parse main^{tree}
  ```

  The two remote `main` commits and local tree hash should match the declared public
  baseline after each synchronization.

## Done criteria

- Private `main` and public `main` have identical commits and tree hashes.
- `202686` is remotely protected and recoverable.
- The private service runs from the synchronized source.
- Every former private-only path has an explicit disposition.
- Any restored private overlay is minimal, tested, documented, and kept off `main`
  unless deliberately upstreamed to public.
