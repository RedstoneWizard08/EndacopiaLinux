#!/bin/bash

set -euo pipefail

if ! python3 -c "import tqdm" > /dev/null 2>&1; then
    echo "Please install python3-tqdm or an equivalent package using your package manager (or install tqdm with pip)."
    exit 1
fi

# This script literally only exists as a convenience
curl -fsSL https://github.com/RedstoneWizard08/EndacopiaLinux/raw/main/install.py | python3
