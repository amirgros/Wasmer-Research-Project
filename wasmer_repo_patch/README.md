# Wasmer Repo Patch

This folder contains a snapshot of uncommitted changes made to a local clone of
[wasmer](https://github.com/wasmerio/wasmer), for the linear memory pool research.

- **Base commit:** `6c15d89cdd3ef20173daad04368d324b3263a07b` (main, 2026-04-27)
- **Patch file:** `wasmer_linear_memory_pool_changes.patch`

## Files changed

- `lib/compiler/src/engine/artifact.rs` (modified)
- `lib/vm/src/instance/mod.rs` (modified)
- `lib/vm/src/lib.rs` (modified)
- `lib/vm/src/memory.rs` (modified)
- `lib/vm/src/mmap.rs` (modified)
- `lib/vm/src/trap/traphandlers.rs` (modified)
- `lib/vm/src/perf_trace.rs` (new)
- `cycles.h` (new)

## How to use

1. Clone the repo:

   ```bash
   git clone git@github.com:wasmerio/wasmer.git
   cd wasmer
   ```

2. Check out the exact base commit this patch was generated against:

   ```bash
   git checkout 6c15d89cdd3ef20173daad04368d324b3263a07b
   ```

3. Apply the patch:

   ```bash
   git apply /path/to/wasmer_repo_patch/wasmer_linear_memory_pool_changes.patch
   ```

   (Use `git apply --check ...` first if you want a dry run without touching the working tree.)

4. Build (see repo `BUILD.md`), e.g. for the C API:

   ```bash
   make build-capi
   ```

## Notes

- The patch was generated with `git diff --cached` after staging all working-tree changes
  (including untracked new files), so it captures both modifications and new files in one
  unified diff.
- If the base commit has since moved on `main`, either `git checkout` the pinned SHA above
  before applying, or expect possible conflicts if applying on top of a newer commit.
