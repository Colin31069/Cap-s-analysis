"""Package the dedicated Python/Tk CAP-S product on the target operating system."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from importlib.util import find_spec
from pathlib import Path

from create_demo_data import create_demo_data

PROJECT = Path(__file__).resolve().parent
VERSION = "1.0.5"
PRODUCT = "CapSStudio"


def make_source_zip(output: Path, examples: Path) -> Path:
    target = output / f"{PRODUCT}-source.zip"
    files = [PROJECT / name for name in (
        "main.py", "requirements-error-band.txt", "run_windows.bat", "run_macos.command",
        "build_windows.bat", "build_portable.py", "create_demo_data.py", "cap_s.spec", "README_PORTABLE.md", "ANALYSIS_METHOD.md",
    )]
    files.extend(sorted((PROJECT / "cap_s").glob("*.py")))
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in files:
            archive.write(file, Path(PRODUCT) / file.relative_to(PROJECT))
        for file in sorted(examples.rglob("*.xlsx")):
            archive.write(file, Path(PRODUCT) / "ExampleData" / file.relative_to(examples))
    return target


def run(arguments: list[str], **options) -> None:
    subprocess.run(arguments, check=True, **options)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=PROJECT.parent / "releases" / "cap-s" / VERSION)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cache = Path(os.environ.get("CAP_S_BUILD_CACHE", Path(tempfile.gettempdir()) / "cap-s-python-build"))
    cache.mkdir(parents=True, exist_ok=True)
    delivered: list[Path] = []

    # Assemble app bundles outside File Provider folders to keep signatures intact.
    with tempfile.TemporaryDirectory(prefix="native-", dir=cache) as directory:
        work = Path(directory)
        examples = work / "ExampleData"
        create_demo_data(examples)
        source = make_source_zip(output, examples)
        delivered.append(source)
        print(f"Source: {source}", flush=True)
        if not args.source_only:
            if sys.platform not in ("darwin", "win32"):
                raise SystemExit("Build native apps on macOS or Windows; use --source-only elsewhere.")
            if find_spec("PyInstaller") is None:
                raise SystemExit("Install PyInstaller into the build environment first.")
            env = os.environ.copy()
            env["PYINSTALLER_CONFIG_DIR"] = str(cache / "pyinstaller-cache")
            env["MPLCONFIGDIR"] = str(cache / "matplotlib-cache")
            env["XDG_CACHE_HOME"] = str(cache / "font-cache")
            dist = work / "dist"
            run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(dist),
                 "--workpath", str(cache / "work"), str(PROJECT / "cap_s.spec")], cwd=PROJECT, env=env)
            suffix = f"macOS-{platform.machine()}" if sys.platform == "darwin" else "Windows"
            share = work / f"{PRODUCT}-{suffix}"
            if sys.platform == "darwin":
                app = dist / f"{PRODUCT}.app"
                for attribute in ("com.apple.FinderInfo", "com.apple.ResourceFork"):
                    run(["xattr", "-dr", attribute, str(app)])
                run(["codesign", "--force", "--deep", "--sign", "-", str(app)])
                run(["codesign", "--verify", "--deep", "--strict", str(app)])
                share.mkdir()
                run(["ditto", "--norsrc", "--noextattr", str(app), str(share / app.name)])
                run(["codesign", "--verify", "--deep", "--strict", str(share / app.name)])
            else:
                shutil.copytree(dist / PRODUCT, share)
            shutil.copytree(examples, share / "ExampleData")
            shutil.copy2(PROJECT / "README_PORTABLE.md", share / "README.md")
            shutil.copy2(PROJECT / "ANALYSIS_METHOD.md", share / "ANALYSIS_METHOD.md")
            archive = work / f"{share.name}.zip"
            if sys.platform == "darwin":
                run(["ditto", "-c", "-k", "--norsrc", "--noextattr", "--keepParent", str(share), str(archive)])
                image_source = work / "dmg"
                shutil.copytree(share, image_source, symlinks=True)
                (image_source / "Applications").symlink_to("/Applications")
                image = work / f"{share.name}.dmg"
                run(["hdiutil", "create", "-volname", "Cap-s data analysis", "-srcfolder", str(image_source),
                     "-ov", "-format", "UDZO", str(image)])
                destination = output / image.name
                shutil.copyfile(image, destination)
                delivered.append(destination)
            else:
                shutil.make_archive(str(archive.with_suffix("")), "zip", root_dir=work, base_dir=share.name)
            destination = output / archive.name
            shutil.copyfile(archive, destination)
            delivered.append(destination)

    shutil.copy2(PROJECT / "README_PORTABLE.md", output / "README.md")
    records = []
    for path in delivered:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        records.append({"file": path.name, "bytes": path.stat().st_size, "sha256": digest})
    (output / "SHA256SUMS.txt").write_text("".join(f"{r['sha256']}  {r['file']}\n" for r in records))
    (output / "manifest.json").write_text(json.dumps({
        "product": "Cap-s data analysis", "version": VERSION, "implementation": "Python/Tk",
        "default_error_band": "SEM", "files": records,
        "windows_status": (
            "Native Windows package built; recipient GUI validation is still required."
            if sys.platform == "win32" and not args.source_only else
            "Deferred until a native Windows build and validation environment is available."
        ),
    }, ensure_ascii=False, indent=2) + "\n")
    for path in delivered:
        print(f"Delivery: {path} ({path.stat().st_size / 1024 / 1024:.2f} MiB)", flush=True)


if __name__ == "__main__":
    main()
