# Skin Analysis Desktop (Tauri)

This folder contains the parallel Rust/Tauri rewrite of the existing Python desktop app.

## Goals

- Keep the Python implementation in `python-app/` stable while migration is in progress
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
npm run tauri dev
npm run tauri build
```

## Notes

- Shared parity cases live in `../shared/parity_cases.json`
- Repository-wide migration rules live in `../MIGRATION_RULES.md`
