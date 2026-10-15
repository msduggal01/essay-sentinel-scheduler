#!/usr/bin/env bash
# ops/thumb_v3_state.sh <artifact-name> <issue> <dest.json>
# The thumbnails v3 rotation state of the last earlier issue: the newest unexpired artifact
# <artifact-name> (one small JSON, uploaded by the daily run) whose issue is below <issue>, copied to
# <dest.json>. Copies nothing when there is none; never fails the job. Needs GH_TOKEN, GITHUB_REPOSITORY.
NAME="$1"; ISSUE="$2"; DEST="$3"
T=$(mktemp -d)
IDS=$(gh api "repos/$GITHUB_REPOSITORY/actions/artifacts?name=$NAME&per_page=20" \
  --jq '[.artifacts[] | select(.expired == false)] | sort_by(.created_at) | reverse | .[].id' 2>/dev/null) || IDS=""
for AID in $IDS; do
  rm -rf "$T/x" && mkdir -p "$T/x"
  gh api "repos/$GITHUB_REPOSITORY/actions/artifacts/$AID/zip" > "$T/a.zip" 2>/dev/null && unzip -o -q "$T/a.zip" -d "$T/x" 2>/dev/null || continue
  F=$(ls "$T"/x/*.json 2>/dev/null | head -1); [ -n "$F" ] || continue
  if python3 - "$F" "$ISSUE" <<'PY' 2>/dev/null
import json, re, sys
t = json.load(open(sys.argv[1]))
num = lambda s: int(re.sub(r"\D", "", str(s)) or 0)
sys.exit(0 if num(t.get("issue")) < num(sys.argv[2]) else 1)
PY
  then
    mkdir -p "$(dirname "$DEST")"; cp "$F" "$DEST"; echo "thumb_v3: rotation state from artifact $AID: $(cat "$DEST")"; break
  fi
done
[ -s "$DEST" ] || echo "thumb_v3: no earlier rotation state for $NAME; the rotation starts fresh"
rm -rf "$T"
exit 0
