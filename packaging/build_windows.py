"""Build a portable, one-folder Windows release with bundled FFmpeg."""

import hashlib
import io
import filecmp
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "release"
DIST = ROOT / "dist"
NAME = "InterPilot_Pro"


def main():
    if sys.platform != "win32":
        raise SystemExit("Windows packaging must run on Windows")

    import imageio_ffmpeg
    from PIL import Image

    # PyInstaller's --noconfirm can replace its output directory.
    for target in (BUILD, DIST, DIST / NAME):
        if not target.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError(f"Build output escapes the workspace: {target}")

    BUILD.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    ffmpeg = BUILD / "ffmpeg.exe"
    ffmpeg_source = Path(imageio_ffmpeg.get_ffmpeg_exe())
    if not ffmpeg.is_file() or not filecmp.cmp(ffmpeg, ffmpeg_source, shallow=False):
        shutil.copy2(ffmpeg_source, ffmpeg)
    icon = BUILD / "InterPilot_Pro.ico"
    with Image.open(ROOT / "logo.png") as logo:
        icon_buffer = io.BytesIO()
        logo.save(icon_buffer, format="ICO", sizes=[(16, 16), (32, 32),
                    (48, 48), (64, 64), (128, 128), (256, 256)])
    icon_bytes = icon_buffer.getvalue()
    if not icon.is_file() or icon.read_bytes() != icon_bytes:
        icon.write_bytes(icon_bytes)

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--onedir", "--windowed", "--noupx",
        "--name", NAME,
        "--icon", str(icon),
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "pyinstaller"),
        "--specpath", str(BUILD),
        "--add-data", f"{ROOT / 'logo.png'}{os.pathsep}.",
        "--add-binary", f"{ffmpeg}{os.pathsep}.",
        "--hidden-import", "whisper",
        "--collect-data", "whisper",
        "--collect-data", "tiktoken",
        "--collect-submodules", "tiktoken_ext",
        str(ROOT / "main.py"),
    ]
    if "--archive-only" not in sys.argv:
        subprocess.run(command, cwd=ROOT, check=True)

    release_dir = DIST / NAME
    exe = release_dir / f"{NAME}.exe"
    if not exe.is_file() or not (release_dir / "_internal" / "ffmpeg.exe").is_file():
        raise RuntimeError("Incomplete bundle: exe or FFmpeg is missing")
    error_file = release_dir / "self-test-error.txt"
    error_file.unlink(missing_ok=True)
    try:
        subprocess.run([str(exe), "--self-test"], cwd=release_dir,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                       check=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        if error_file.exists():
            print(error_file.read_text(encoding="utf-8"), file=sys.stderr)
        raise
    (release_dir / "START_HERE.txt").write_text(
        "InterPilot Pro Windows portable release\n\n"
        "1. Extract the entire archive to a writable folder.\n"
        "2. Run InterPilot_Pro.exe; keep the _internal folder beside it.\n"
        "3. Configure your model and audio devices in Settings.\n"
        "4. Local Whisper downloads its model on first use.\n\n"
        "Settings and exported sessions are stored beside this exe.\n"
        "For installation under Program Files, grant write access or use a portable folder.\n",
        encoding="utf-8",
    )
    shutil.copyfile(ROOT / "packaging" / "FFmpeg-GPL-3.0.txt",
                    release_dir / "FFmpeg-GPL-3.0.txt")
    for readme in ("README.md", "README_en.md"):
        shutil.copyfile(ROOT / readme, release_dir / readme)
    ffmpeg_version = subprocess.run(
        [str(ffmpeg), "-version"], capture_output=True, text=True, check=True
    ).stdout.splitlines()[0]
    (release_dir / "THIRD_PARTY_NOTICES.txt").write_text(
        "Bundled FFmpeg executable\n"
        f"{ffmpeg_version}\n"
        "Source distribution: https://www.gyan.dev/ffmpeg/builds/\n"
        "FFmpeg source: https://ffmpeg.org/download.html#get-sources\n"
        "The bundled FFmpeg build reports GPL version 3 or later. "
        "Its license text is in FFmpeg-GPL-3.0.txt.\n",
        encoding="utf-8",
    )
    archive = Path(shutil.make_archive(str(DIST / f"{NAME}-windows-x64"), "zip", DIST, NAME))
    hasher = hashlib.sha256()
    with archive.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    (DIST / f"{archive.name}.sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="ascii"
    )
    print(f"Release: {archive} ({archive.stat().st_size / 1_000_000:.1f} MB)")
    print(f"SHA256: {digest}")


if __name__ == "__main__":
    main()
