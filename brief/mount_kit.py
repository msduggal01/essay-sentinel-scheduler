#!/usr/bin/env python3
"""mount_kit.py: hand the brief kit to a managed-agent session as mounted files.

The agents' sandboxes cannot reach GitHub, so the workflow that starts the session (which can)
uploads the kit through the Files API and attaches it as session resources, mounted read-only
at /workspace/brief/. Run on the GitHub runner, with ANTHROPIC_API_KEY set:

    python3 mount_kit.py resources > kit_resources.json   # upload; print the resources list
    ... create the session with "resources": <that list> ...
    python3 mount_kit.py cleanup                          # delete the uploaded originals

The session keeps its own copy of each file, so the originals can be deleted once the
session exists. If anything fails, "resources" prints [] and exits 0: the session starts
without the kit and the agent falls back as its prompt says.
"""
import json, os, sys, urllib.request, uuid

RAW = "https://raw.githubusercontent.com/msduggal01/essay-sentinel-scheduler/main/brief/"
FILES = ["briefkit.py", "brief_build.py", "SCHEMA.md", "examples/sociology.json", "examples/essay.json"]
MOUNT = "/workspace/brief/"
IDS = ".kit_file_ids"
API = "https://api.anthropic.com/v1/files"
H = {"x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""), "anthropic-version": "2023-06-01",
     "anthropic-beta": "files-api-2025-04-14"}


def upload(name, data):
    b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\nagent\r\n"
            f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{os.path.basename(name)}\"\r\n"
            f"Content-Type: text/plain\r\n\r\n").encode() + data + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(API, data=body, method="POST", headers=dict(H, **{"Content-Type": f"multipart/form-data; boundary={b}"}))
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["id"]


def resources():
    out, ids = [], []
    try:
        for f in FILES:
            src = os.path.join(os.path.dirname(os.path.abspath(__file__)), f)
            data = open(src, "rb").read() if os.path.isfile(src) and "--download" not in sys.argv \
                else urllib.request.urlopen(RAW + f, timeout=60).read()
            fid = upload(f, data); ids.append(fid)
            out.append({"type": "file", "file_id": fid, "mount_path": MOUNT + f})
    except Exception as e:
        print(f"mount_kit: kit not attached ({str(e)[:200]})", file=sys.stderr)
        open(IDS, "w").write("\n".join(ids)); cleanup()
        print("[]"); return
    open(IDS, "w").write("\n".join(ids))
    print(json.dumps(out))
    print(f"mount_kit: {len(out)} kit files attached at {MOUNT}", file=sys.stderr)


def cleanup():
    if not os.path.isfile(IDS):
        return
    for fid in filter(None, open(IDS).read().split()):
        try:
            urllib.request.urlopen(urllib.request.Request(f"{API}/{fid}", method="DELETE", headers=H), timeout=60)
        except Exception as e:
            print(f"mount_kit: could not delete {fid} ({str(e)[:120]})", file=sys.stderr)
    os.remove(IDS)


if __name__ == "__main__":
    {"resources": resources, "cleanup": cleanup}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
