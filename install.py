#!/usr/bin/env python3
# ruff: noqa: I001

import os
import sys
import stat
import shutil
import hashlib
import tarfile
import requests
import subprocess

from tqdm import tqdm

APP_ID = "2684630"
APP_NAME = "Endacopia"
GAME_DIR = os.environ.get("GAME_DIR", None)  # Set if your install is in a weird place

AGS_VERSION = "3.6.0.55"
AGSTEAM_VERSION = "3.4"
AGSSHELL_PIN = "81143ca1de10ff4bb1342da5b9ed4528b61ab139"

CXX = "g++"
DEFINES = ["-DNDEBUG"]
CXXFLAGS = ["-g", "-O2", "-Wall", "-fPIC", *DEFINES]

LD = "g++"
LDFLAGS: list[str] = []

LOG_PREFIX = "\x1b[0;95m>> \x1b[0m"


def log(msg: str):
    print(f"{LOG_PREFIX}\x1b[1;96m{msg}\x1b[0m")


def log_err(msg: str):
    print(f"{LOG_PREFIX}\x1b[1;91m{msg}\x1b[0m")


step = 0
n_steps = 0


def log_step(msg: str):
    print(f"{LOG_PREFIX}\x1b[1;97m[{step} / {n_steps}] \x1b[1;95m{msg}\x1b[0m")


def find_via_steam(app_id: str, game_name: str):
    libs_file = os.path.join(
        os.environ["HOME"], ".local/share/Steam/steamapps/libraryfolders.vdf"
    )

    with open(libs_file, "r") as f:
        raw = f.readlines()

    candidates: list[str] = []

    for line in raw:
        if line.strip().startswith('"path"'):
            line = line.strip().split('"')[3]

            candidates.append(line)

    for path in candidates:
        acf_path = os.path.join(path, f"steamapps/appmanifest_{app_id}.acf")

        if not os.path.exists(acf_path):
            continue

        game_path = os.path.join(path, f"steamapps/common/{game_name}")

        if not os.path.exists(game_path):
            log_err(f"Found .acf manifest but game path doesn't exist: {game_path}")
            sys.exit(1)

        return game_path

    return None


def strip_tar_members(tar: tarfile.TarFile, strip_components: int):
    for member in tar.getmembers():
        member.path = member.path.split("/", strip_components)[-1]
        yield member


if GAME_DIR == None or GAME_DIR == "" or not os.path.exists(GAME_DIR):
    GAME_DIR = find_via_steam(APP_ID, APP_NAME)

if GAME_DIR == None or GAME_DIR == "" or not os.path.exists(GAME_DIR):
    log_err(f"Failed to find {APP_NAME} install!")
    sys.exit(1)

log(f"Found {APP_NAME} at: \x1b[1;92m{GAME_DIR}\x1b[0m")

out_dir = os.path.join(GAME_DIR, "Linux")
work_dir = os.path.join(GAME_DIR, ".work")


def download_file(url: str, name: str, target: str) -> None:
    tmp_path = f"{target}.tmp"

    res = requests.get(url, stream=True)
    res.raise_for_status()

    total = int(res.headers.get("content-length", 0))
    chk_size = 256

    os.makedirs(os.path.dirname(target), exist_ok=True)

    with (
        open(tmp_path, "wb") as f,
        tqdm(
            desc=f"   {name}",
            total=total,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
            ascii=True,
            bar_format="\x1b[1;94m{desc}: \x1b[0;96m{percentage:3.0f}% [{bar}\x1b[0;96m] \x1b[0;92m{n_fmt}/{total_fmt} \x1b[0;96m[{elapsed} <{remaining}, {rate_fmt}{postfix}]\x1b[0m",
            # im american so this tripped me up ngl LMAO
            colour="magenta",
        ) as pb,
    ):
        for chk in res.iter_content(chunk_size=chk_size):
            size = f.write(chk)
            pb.update(size)

    os.rename(tmp_path, target)


def install_ags() -> None:
    tar_name = f"ags_{AGS_VERSION}_linux.tar.gz"
    tar_path = os.path.join(work_dir, tar_name)

    tar_url = f"https://github.com/adventuregamestudio/ags/releases/download/v{AGS_VERSION}/{tar_name}"
    csum_url = f"https://github.com/adventuregamestudio/ags/releases/download/v{AGS_VERSION}/checksums.sha256"

    log_step("Installing AGS runtime...")

    def check_sums(display: bool):
        if not os.path.exists(tar_path):
            return False

        content = requests.get(csum_url).text.splitlines()
        line: str = next(filter(lambda x: x.endswith(tar_name), content))
        line = line.split(" ")[0]

        with open(tar_path, "rb") as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()

        if sha256 != line:
            if display:
                print(f"   \x1b[0;95m{tar_name}: \x1b[1;91mINVALID\x1b[0m")

            return False

        if display:
            print(f"   \x1b[0;95m{tar_name}: \x1b[1;92mVALID\x1b[0m")

        return True

    if not os.path.exists(tar_path) or not check_sums(False):
        print("   \x1b[0;95mDownloading archive...\x1b[0m")

        download_file(tar_url, tar_name, tar_path)

    print("   \x1b[0;95mChecking archive integrity...\x1b[0m")

    check_sums(True)

    print("   \x1b[0;95mExtracting archive...\x1b[0m")

    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(out_dir)


def install_agsteam() -> None:
    tar_name = f"agsteam-linux-{AGSTEAM_VERSION}-all.tar.gz"
    tar_path = os.path.join(work_dir, tar_name)
    tmp_path = os.path.join(work_dir, "agsteam-tmp")

    tar_url = f"https://github.com/monkey0506/agsteam/releases/download/v{AGSTEAM_VERSION}/{tar_name}"

    log_step("Installing agsteam...")

    if not os.path.exists(tar_path):
        print("   \x1b[0;95mDownloading archive...\x1b[0m")

        download_file(tar_url, tar_name, tar_path)

    print("   \x1b[0;95mExtracting archive...\x1b[0m")

    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(tmp_path)

    print("   \x1b[0;95mCopying files...\x1b[0m")

    to_copy = {
        os.path.join(tmp_path, "Release/linux32"): os.path.join(out_dir, "data/lib32"),
        os.path.join(tmp_path, "Release/linux64"): os.path.join(out_dir, "data/lib64"),
    }

    for from_, to in to_copy.items():
        for file in os.listdir(from_):
            real = os.path.join(from_, file)
            out = os.path.join(to, file)

            shutil.copyfile(real, out)


def install_agsshell() -> None:
    log_step("Installing ags_shell...")

    tar_name = f"agsshell-{AGSSHELL_PIN}.tar.gz"
    tar_path = os.path.join(work_dir, tar_name)
    tmp_path = os.path.join(work_dir, "agsshell-tmp")

    src = os.path.join(tmp_path, "agsshell.cpp")

    obj64 = os.path.join(tmp_path, "agsshell.x86_64.o")
    obj32 = os.path.join(tmp_path, "agsshell.i686.o")

    so64 = os.path.join(tmp_path, "libags_shell.x86_64.so")
    so32 = os.path.join(tmp_path, "libags_shell.i686.so")

    so64_out = os.path.join(out_dir, "data/lib64/libags_shell.so")
    so32_out = os.path.join(out_dir, "data/lib32/libags_shell.so")

    tar_url = f"https://github.com/ericoporto/agsshell/archive/{AGSSHELL_PIN}.tar.gz"

    if not os.path.exists(tar_path):
        print("   \x1b[0;95mDownloading archive...\x1b[0m")

        download_file(tar_url, tar_name, tar_path)

    print("   \x1b[0;95mExtracting archive...\x1b[0m")

    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(tmp_path, members=strip_tar_members(tar, 1))

    def print_cmd(file: str, out: str, flags: list[str], exe: str) -> None:
        rel_file = os.path.relpath(file, tmp_path)
        rel_out = os.path.relpath(out, tmp_path)

        cmdline = [exe, *flags, "-o", out, file]

        fmt = f"\x1b[2;32m{exe} \x1b[2;34m{' '.join(flags)} \x1b[2;37m-o \x1b[2;33m{rel_out} \x1b[2;36m{rel_file}\x1b[0m"

        print(f"   \x1b[2;37mexec: \x1b[0m{fmt}")
        subprocess.check_output(cmdline)

    def compile(file: str, out: str, extra_flags: list[str]) -> None:
        print_cmd(file, out, [*CXXFLAGS, *extra_flags], CXX)

    def link(file: str, out: str, extra_flags: list[str]) -> None:
        print_cmd(file, out, [*LDFLAGS, *extra_flags], LD)

    print("   \x1b[0;95mCompiling 64-bit library...\x1b[0m")

    compile(src, obj64, ["-c", "-m64"])
    link(obj64, so64, ["-shared", "-m64"])

    print("   \x1b[0;95mCompiling 32-bit library...\x1b[0m")

    compile(src, obj32, ["-c", "-m32"])
    link(obj32, so32, ["-shared", "-m32"])

    print("   \x1b[0;95mCopying libraries...\x1b[0m")

    shutil.copyfile(so64, so64_out)
    shutil.copyfile(so32, so32_out)


LAUNCHER = """
#!/bin/sh
scriptpath=$(readlink -f "$0")
scriptdir=$(dirname "$scriptpath")
#datadir="$scriptdir/data/"
datadir="$scriptdir/../Data"

for arg; do
    if [ "$arg" = "--help" ]; then
        printf "Usage: %s [<ags options>]\\n\\n" "$(basename "$0")"
        break
    fi
done

## Old versions of Mesa can hang when using DRI3
## https://bugs.freedesktop.org/show_bug.cgi?id=106404
export LIBGL_DRI3_DISABLE=true

if [ "$(uname -m)" = "x86_64" ]; then
    ALLEGRO_MODULES="$scriptdir/data/lib64" "$scriptdir/data/ags64" "$@" "$datadir"
else
    ALLEGRO_MODULES="$scriptdir/data/lib32" "$scriptdir/data/ags32" "$@" "$datadir"
fi
"""

WRAPPER = """
#!/bin/bash

total=$#
args=("${@:1:total-3}")
pwd="$(dirname "$(realpath "$0")")"

"${args[@]}" bash "$pwd/Endacopia"
"""


def install_launcher() -> None:
    steam_appid_path = os.path.join(out_dir, "steam_appid.txt")
    launcher_path = os.path.join(out_dir, "Endacopia")
    wrapper_path = os.path.join(out_dir, "wrapper.sh")

    log_step("Installing launcher files...")

    print("   \x1b[0;95mCreating steam_appid.txt...\x1b[0m")

    with open(steam_appid_path, "w") as f:
        f.write(str(APP_ID))

    print("   \x1b[0;95mCreating launcher...\x1b[0m")

    with open(launcher_path, "w") as f:
        f.write(LAUNCHER.strip() + "\n")

    print("   \x1b[0;95mCreating wrapper...\x1b[0m")

    with open(wrapper_path, "w") as f:
        f.write(WRAPPER.strip() + "\n")

    current_mode = os.stat(wrapper_path).st_mode

    # chmod a+rx
    os.chmod(
        wrapper_path,
        current_mode
        | stat.S_IRUSR
        | stat.S_IXUSR
        | stat.S_IRGRP
        | stat.S_IXGRP
        | stat.S_IROTH
        | stat.S_IXOTH,
    )

    print("   \x1b[0;95mRemoving old files...\x1b[0m")

    os.remove(os.path.join(out_dir, "startgame"))
    os.remove(os.path.join(out_dir, "README"))


def clean_up() -> None:
    log_step("Cleaning up...")

    print("   \x1b[0;95mCleaning up work dir...\x1b[0m")

    shutil.rmtree(work_dir)


steps = [
    install_ags,
    install_agsteam,
    install_agsshell,
    install_launcher,
    clean_up,
]

n_steps = len(steps)

for step_fn in steps:
    step += 1
    step_fn()

log("All done!")
