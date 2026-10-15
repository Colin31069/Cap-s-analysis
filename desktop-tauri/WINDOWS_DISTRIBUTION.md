# Windows distribution

The Windows build produces an unsigned x64 NSIS setup executable. It embeds the WebView2 offline installer, so a recipient does not need Python, Node.js, Rust, or a separate WebView2 download. The setup file is larger because it includes the complete WebView2 runtime; its size depends on the runtime version.

## Build

Use a macOS host with Node.js, Rust, LLVM (`llvm-rc` and `lld-link`), NSIS (`makensis`), and `cargo-xwin` installed. The cross-platform Tauri build is experimental; use Windows for a native release when available. On macOS these tools can be installed with `brew install llvm lld makensis` and `cargo install --locked cargo-xwin`.

On Windows, the same wrapper uses native MSVC compilation and does not require `cargo-xwin`, Homebrew, or LLVM. Install the Tauri Windows prerequisites (Rust, Node.js, and Visual Studio C++ Build Tools with a Windows SDK), then use the commands below.

```sh
cd desktop-tauri
npm ci
npm run deps:prepare
rustup target add x86_64-pc-windows-msvc
node scripts/build-windows.mjs
```

Use `node scripts/build-windows.mjs --cached` when `dist/` is already current.

The build uses a separate Windows Cargo target directory under the operating system's temporary directory by default and writes the release to `releases/<version>/windows/`:

- `Skin Analysis Desktop_<version>_x64-setup.exe`
- `README.txt` with recipient instructions
- `SHA256SUMS.txt`

Set `CAP_S_PACKAGING_ROOT` to use a different task-local cache root. `CARGO_TARGET_DIR` and `XWIN_CACHE_DIR` can also be set directly. Windows x64 builds on this host use `/private/tmp/cap-s-packaging/target-windows` and `/private/tmp/cap-s-packaging/xwin`.

The build script checks the application binary's PE architecture and verifies that the generated NSIS script points to a real offline WebView2 installer payload. Cross-compilation does not verify installation or runtime behavior on Windows; smoke-test the installer on a clean Windows 10/11 x64 machine before external distribution.
