# Skin Analysis Desktop (Tauri)

This folder contains the parallel Rust/Tauri rewrite of the existing Python desktop app.

## Goals

- Keep the Python implementation in `Python version/` stable while migration is in progress
- Recreate the same end-user workflow with a smaller cross-platform packaging target
- Preserve the same analysis contract and parity-test expectations as the Python version

## Planned Stack

- Rust for filesystem access, Excel parsing, signal analysis, and payload generation
- Tauri for desktop packaging on macOS and Windows
- Svelte + TypeScript for the UI
- Plotly.js for interactive plotting and PNG export

## Commands

Once Rust, Node.js, and the Tauri toolchain are installed locally:

```bash
npm install
npm run deps:prepare
npm run tauri dev
npm run tauri:build
```

The dev/build scripts copy Plotly from `node_modules` into `public/vendor/` and the UI loads it only when a plot is first rendered. This keeps the initial Vite/Tauri startup path small while preserving offline packaging.

Use `npm run deps:prepare` before packaging on a fresh machine to install npm packages, sync frontend vendor assets, and fetch Cargo crates into the local Cargo cache. For a fully project-local Cargo source mirror, run `npm run deps:vendor`; it creates `src-tauri/vendor/` and `src-tauri/.cargo/config.toml` so Cargo reads crate sources from the project instead of the registry cache.

Packaging now defaults to the host platform's native Tauri bundle targets. Use the platform-specific commands below when you need a deterministic output.

### macOS packaging

Run these commands on a macOS host:

```bash
cd desktop-tauri
npm run tauri:build:mac
```

The macOS command prepares npm/Cargo dependencies, builds the frontend, and collects the delivery files under:

```text
../releases/<version>/macos/
```

The compiler output uses `CARGO_TARGET_DIR` when set, or `cap-s-packaging/target-macos/` under the operating system's temporary directory. This keeps build caches separate from the files sent to recipients.

For a universal Apple Silicon + Intel build, install both Rust targets once and then run the universal script:

```bash
rustup target add aarch64-apple-darwin x86_64-apple-darwin
npm run tauri:build:mac:universal
```

Use `npm run tauri:build:mac:cached` when `dist/` and Cargo dependencies are already current to skip dependency preparation and the frontend rebuild. Add `-- --cached` to the universal command for the same behavior.

Unsigned local builds are useful for internal testing. For distribution outside your own machine, sign and notarize the app with an Apple Developer ID certificate.

The macOS wrapper stages the `.dmg` and `.app.zip` in `../releases/<version>/macos/`, with recipient instructions and SHA-256 checksums. Both contain the signed `.app`; temporary app staging stays outside File Provider folders to keep Finder metadata from invalidating its signature. It uses the existing Developer ID Application identity when available and otherwise signs ad-hoc. Notarization is a separate release step; ad-hoc builds can prompt or be blocked by Gatekeeper on another Mac. Universal builds contain both Apple Silicon and Intel binaries; deployment targets are checked in the finished bundle.

### Windows packaging

```bash
npm run tauri:build:win
npm run tauri:build:all
```

`tauri:build:win` builds an x64 NSIS installer on Windows, or uses `cargo-xwin` when run on macOS. It embeds the WebView2 offline installer and stages the setup executable, instructions, and SHA-256 checksum in `../releases/<version>/windows/`. Recipients do not need Python, Node.js, Rust, or a separate WebView2 download. See [WINDOWS_DISTRIBUTION.md](./WINDOWS_DISTRIBUTION.md) for cross-build prerequisites and verification limits.

Use `npm run tauri:build:exe` to compile the release app without producing an installer.

When the frontend has already been built and `dist/` is current, use `npm run tauri:build:exe:cached`, `npm run tauri:build:win:cached`, or `npm run tauri:build:cached` to skip the frontend rebuild. This avoids rewriting `dist/`, which would otherwise force Tauri to relink the embedded assets.

## Notes

- Shared parity cases live in `../shared/parity_cases.json`
- Repository-wide migration rules live in `../MIGRATION_RULES.md`
