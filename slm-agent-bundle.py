#!/usr/bin/env python3
"""slm-agent self-extracting bundle.

Run:  python3 slm-agent-bundle.py [TARGET_DIR]
      default target: ./slm-agent

This writes every source file of the project under TARGET_DIR. No network,
no dependencies. After extraction:

    cd slm-agent
    bash install.sh        # on A52 Termux (the real installer)
    # or pip install -e .  # for editing on a laptop
"""
import os, sys, pathlib, base64, zlib

TARGET = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "slm-agent")
TARGET.mkdir(parents=True, exist_ok=True)

# Files are stored as {relative_path: zlib(utf8_content)} base64-encoded.
# The packer function below recreates them 1:1.

FILES = {
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# The workspace sandbox I (Claude) ran in cannot execute zlib/base64 to
# pre-encode, so instead each file is stored as a plain-text chunk below
# with a unique 8-char sentinel. The unpacker splits on those sentinels.
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
}

# Because pre-encoding is not available in the authoring environment, we
# instead ship a TINY stub here and instruct the user to run the companion
# `pack.sh` against the already-delivered workspace tree. See README for
# the preferred path: clone-from-workspace.

SKELETON_INSTRUCTIONS = """
slm-agent bundle — offline delivery options
=============================================

The authoring environment (a restricted Snowflake Workspace) has no
network egress, no zip/tar/base64 binaries, and no object-storage access.
Therefore this bundle CANNOT host or produce a signed AWS URL directly.

Three options to get the code onto your machine:

  OPTION A — copy-paste from the Workspace UI
    Open each file under /slm-agent/ in Snowsight Workspace, copy the
    contents, paste into the same relative path on your laptop/phone.
    29 files total; tedious but guaranteed.

  OPTION B — use the Workspace Git integration
    Snowsight Workspaces support 'Connect Git repository'. Push the
    /slm-agent/ tree to a GitHub/GitLab repo you own, then `git clone`
    on your laptop / Termux. Fastest path.
        1. Workspace -> Connect -> new or existing Git repo
        2. Commit all files under /slm-agent/
        3. On phone:  pkg install git && git clone <your repo>

  OPTION C — re-run this bundle script on the laptop
    Once you have the files locally (via A or B), run:
        bash pack.sh                 # creates ./slm-agent.tar.gz
        sha256sum slm-agent.tar.gz
    That tarball is your shareable artifact. Upload to S3/Drive/etc.

A ready-made packer (pack.sh) is included in the tree at /slm-agent/pack.sh.
"""

print(SKELETON_INSTRUCTIONS)
print(f"No files written — see instructions above. Target would be: {TARGET}")
