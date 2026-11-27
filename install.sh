#!/bin/bash

set -euo pipefail

APP_ID="2684630"
GAME_DIR="" # Set if your install is in a weird place

AGS_VERSION="3.6.0.55"
AGSTEAM_VERSION="3.4"
AGSSHELL_PIN="81143ca1de10ff4bb1342da5b9ed4528b61ab139"

log_step() {
    echo -e ">> \x1b[1;45;97m[$1/5]\x1b[0m\x1b[1;96m $2\x1b[0m"
}

log_msg() {
    echo -e ">> \x1b[1;96m$1\x1b[0m"
}

log_dbg() {
    echo -e ">> \x1b[1;93m$1\x1b[0m"
}

log_err() {
    echo -e ">> \x1b[1;91m$1\x1b[0m"
}

if [[ -z "$GAME_DIR" ]]; then
    mapfile -t PATHS < <(grep -oP '"path"\s+"\K[^"]+' "$HOME/.local/share/Steam/steamapps/libraryfolders.vdf")

    log_msg "Looking for Endacopia through Steam..."

    for LIB in "${PATHS[@]}"; do
        log_dbg "Checking in $LIB..."

        MANIFEST="$LIB/steamapps/appmanifest_${APP_ID}.acf"

        if [[ -f "$MANIFEST" ]]; then
            INSTALL_DIR="$(grep -oP '"installdir"\s+"\K[^"]+' "$MANIFEST")"
            GAME_DIR="$LIB/steamapps/common/$INSTALL_DIR"

            log_msg "Found Endacopia at: $GAME_DIR"
            break
        fi
    done

    if [[ -z "$GAME_DIR" ]]; then
        log_err "Failed to find Endacopia through Steam."
        exit 1
    fi
fi

OUT_DIR="$GAME_DIR/Linux"
WORK_DIR="$GAME_DIR/.work"

mkdir -p "$OUT_DIR"
mkdir -p "$WORK_DIR"

# AGS

log_step 1 "Installing AGS runtime..."
echo ""

AGS_TAR_NAME="ags_${AGS_VERSION}_linux.tar.gz"
AGS_TAR="$WORK_DIR/$AGS_TAR_NAME"

[[ ! -f "$AGS_TAR" ]] && wget -qO "$AGS_TAR" --show-progress \
    "https://github.com/adventuregamestudio/ags/releases/download/v${AGS_VERSION}/$AGS_TAR_NAME"

pushd "$WORK_DIR" > /dev/null

curl -fsSL "https://github.com/adventuregamestudio/ags/releases/download/v${AGS_VERSION}/checksums.sha256" |
    grep "$AGS_TAR_NAME" |
    sha256sum -c -

popd > /dev/null

tar -C "$OUT_DIR" -xzf "$AGS_TAR"

# agsteam

echo ""
log_step 2 "Installing agsteam..."

AGSTEAM_TAR_NAME="agsteam-linux-${AGSTEAM_VERSION}-all.tar.gz"
AGSTEAM_TAR="$WORK_DIR/$AGSTEAM_TAR_NAME"
AGSTEAM_TMP="$WORK_DIR/agsteam-tmp"

[[ ! -f "$AGSTEAM_TAR" ]] && wget -qO "$AGSTEAM_TAR" --show-progress \
    "https://github.com/monkey0506/agsteam/releases/download/v${AGSTEAM_VERSION}/$AGSTEAM_TAR_NAME"

mkdir -p "$AGSTEAM_TMP"

tar -C "$AGSTEAM_TMP" -xzf "$AGSTEAM_TAR"
cp "$AGSTEAM_TMP/Release/linux32/"* "$OUT_DIR/data/lib32/"
cp "$AGSTEAM_TMP/Release/linux64/"* "$OUT_DIR/data/lib64/"

# agsshell

log_step 3 "Downloading agsshell..."

AGSSHELL_TAR="$WORK_DIR/agsshell-${AGSSHELL_PIN}.tar.gz"
AGSSHELL_TMP="$WORK_DIR/agsshell-tmp"

[[ ! -f "$AGSSHELL_TAR" ]] && wget -qO "$AGSSHELL_TAR" --show-progress "https://github.com/ericoporto/agsshell/archive/${AGSSHELL_PIN}.tar.gz"

mkdir -p "$AGSSHELL_TMP"

tar -C "$AGSSHELL_TMP" --strip-components 1 -xzf "$AGSSHELL_TAR"

# agsshell build

log_step 4 "Building agsshell..."
echo ""

run() {
    echo "$*"
    "$@"
}

SRC="$AGSSHELL_TMP/agsshell.cpp"

OBJ64="$AGSSHELL_TMP/agsshell.x86_64.o"
OBJ32="$AGSSHELL_TMP/agsshell.i686.o"

SO64="$AGSSHELL_TMP/libags_shell.x86_64.so"
SO32="$AGSSHELL_TMP/libags_shell.i686.so"

CXX="g++"
CXXFLAGS=("-c" "-g" "-O2" "-Wall" "-fPIC")

LD="g++"
LDFLAGS=("-shared")

printcmd() {
    echo -e "\x1b[0;35m$1 \x1b[0;34m$2 \x1b[0;37m-o \x1b[0;33m$(realpath --relative-to "$AGSSHELL_TMP" "$3") \x1b[0;36m$(realpath --relative-to "$AGSSHELL_TMP" "$4")\x1b[0m"
}

printcmd "$CXX" "${CXXFLAGS[*]}" "$OBJ64" "$SRC"
"$CXX" "${CXXFLAGS[@]}" -o "$OBJ64" "$SRC"

printcmd "$CXX" "-m32 ${CXXFLAGS[*]}" "$OBJ32" "$SRC"
"$CXX" -m32 "${CXXFLAGS[@]}" -o "$OBJ32" "$SRC"

printcmd "$LD" "${LDFLAGS[*]}" "$SO64" "$OBJ64"
"$LD" "${LDFLAGS[@]}" -o "$SO64" "$OBJ64"

printcmd "$LD" "-m32 ${LDFLAGS[*]}" "$SO32" "$OBJ32"
"$LD" -m32 "${LDFLAGS[@]}" -o "$SO32" "$OBJ32"

cp "$SO64" "$OUT_DIR/data/lib64/libags_shell.so"
cp "$SO32" "$OUT_DIR/data/lib32/libags_shell.so"

# finish

echo ""
log_step 5 "Finishing up..."

cp "$GAME_DIR/Windows/steam_appid.txt" "$OUT_DIR"

cat << 'EOF' > "$OUT_DIR/Endacopia"
#!/bin/sh
scriptpath=$(readlink -f "$0")
scriptdir=$(dirname "$scriptpath")
#datadir="$scriptdir/data/"
datadir="$scriptdir/../Data"

for arg; do
    if [ "$arg" = "--help" ]; then
        printf "Usage: %s [<ags options>]\n\n" "$(basename "$0")"
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
EOF

chmod a+rx "$OUT_DIR/Endacopia"

rm "$OUT_DIR/startgame"
rm "$OUT_DIR/README"

# Clean up

rm -r "$WORK_DIR"

log_msg "All done!"
