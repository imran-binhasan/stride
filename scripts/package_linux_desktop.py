"""Package the validated Linux native binary as a local Debian installer."""

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--binary", type=Path, default=root / "artifacts/desktop/stride-companion-linux-x86_64"
)
parser.add_argument(
    "--output", type=Path, default=root / "artifacts/desktop/stride-companion_0.1.0_amd64.deb"
)
args = parser.parse_args()
if not args.binary.is_file():
    raise SystemExit("Build or export the native Linux binary first")
with tempfile.TemporaryDirectory(prefix="stride-deb-") as directory:
    package = Path(directory)
    for path in [
        "DEBIAN",
        "usr/bin",
        "usr/share/applications",
        "usr/share/icons/hicolor/128x128/apps",
    ]:
        (package / path).mkdir(parents=True)
    binary = package / "usr/bin/stride-companion"
    shutil.copyfile(args.binary, binary)
    binary.chmod(0o755)
    shutil.copyfile(
        root / "desktop/src-tauri/icons/icon.png",
        package / "usr/share/icons/hicolor/128x128/apps/stride-companion.png",
    )
    (package / "usr/share/applications/stride-companion.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Stride Companion\nComment=Project time and activity tracker\nExec=/usr/bin/stride-companion\nIcon=stride-companion\nTerminal=false\nCategories=Office;ProjectManagement;\n"
    )
    (package / "DEBIAN/control").write_text(
        "Package: stride-companion\nVersion: 0.1.0\nArchitecture: amd64\nMaintainer: A3Zen\nSection: utils\nPriority: optional\nDepends: libgtk-3-0, libwebkit2gtk-4.1-0, libayatana-appindicator3-1, libssl3, libx11-6, libxcb1, libgbm1, libpipewire-0.3-0, libdbus-1-3, libegl1, libwayland-client0, libwayland-server0\nDescription: Stride native project time and activity companion\n Authenticated task timers, privacy controls, screenshots, and activity summaries.\n"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["dpkg-deb", "--build", "--root-owner-group", str(package), str(args.output)], check=True
    )
