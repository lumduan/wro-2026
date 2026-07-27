#!/usr/bin/env bash
# Archive the EV3 and SPIKE toolchains before they stop being downloadable.
#
# NEEDS-VERIFY(ev3-download-window): third-party sources put the EV3 app download
# cutoff at 31 July 2026; LEGO's own retired-products page states no date. The
# verification status does not change the decision -- archiving costs minutes and
# missing the window is permanent.
#
# Records a sha256 for everything it gets, AND records what it could not get and
# why. The second list is the deliverable: it says what is still at risk.
#
#   tools/archive_toolchains.sh                 fetch and record
#   tools/archive_toolchains.sh --dry-run       list targets, fetch nothing
#   tools/archive_toolchains.sh --record-only FILE ID
#                                               hash a hand-downloaded file into
#                                               the manifest (for login-gated ones)
#
# See docs/TOOLCHAIN_ARCHIVE.md.

set -uo pipefail   # deliberately NOT -e: one failed fetch must not abort the rest

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/archive/toolchains"
MANIFEST="$DEST/MANIFEST.json"
TODAY="$(date +%F)"
DRY_RUN=0

# id|host|url  -- LEGO-hosted first: those are the ones that disappear.
# URLs are landing pages where the direct artifact is behind a chooser or a
# login; the script records the page and marks the artifact manual_only rather
# than guessing a download path that may 404 silently.
TARGETS=(
  "ev3-micropython-image|lego|https://pybricks.com/ev3-micropython/"
  "ev3-lab|lego|https://education.lego.com/en-us/downloads/retiredproducts/"
  "ev3-classroom|lego|https://education.lego.com/en-us/downloads/retiredproducts/"
  "ev3-firmware|lego|https://education.lego.com/en-us/downloads/retiredproducts/"
  "spike-app|lego|https://education.lego.com/en-us/downloads/spike-app/software/"
  "pybricks-micropython|github|https://api.github.com/repos/pybricks/pybricks-micropython/releases/latest"
  "ev3dev-lang-python|github|https://api.github.com/repos/ev3dev/ev3dev-lang-python/releases/latest"
)

log() { printf '  %s\n' "$*"; }

# --- record-only: hash a file someone downloaded by hand -------------------- #
if [[ "${1:-}" == "--record-only" ]]; then
  file="${2:?usage: --record-only FILE ID}"; id="${3:?usage: --record-only FILE ID}"
  [[ -f "$file" ]] || { echo "no such file: $file" >&2; exit 1; }
  mkdir -p "$DEST"
  printf '{"id":"%s","status":"obtained","source":"manual","bytes":%s,"sha256":"%s","obtained_at":"%s"}\n' \
    "$id" "$(stat -c%s "$file")" "$(sha256sum "$file" | cut -d' ' -f1)" "$TODAY" \
    >> "$DEST/manual-records.jsonl"
  echo "recorded $id -> $DEST/manual-records.jsonl"
  exit 0
fi

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

mkdir -p "$DEST"
echo "archive -> $DEST"
[[ $DRY_RUN -eq 1 ]] && echo "(dry run: nothing will be fetched)"
echo

obtained=(); missed=()

for entry in "${TARGETS[@]}"; do
  IFS='|' read -r id host url <<< "$entry"
  echo "[$host] $id"

  if [[ $DRY_RUN -eq 1 ]]; then log "would fetch $url"; continue; fi

  if [[ "$host" == "github" ]]; then
    # Pin by tag AND commit: a tag can move or be deleted, a commit hash cannot.
    meta="$DEST/${id}.release.json"
    if curl -fsSL --max-time 60 "$url" -o "$meta" 2>/dev/null; then
      tag=$(grep -m1 '"tag_name"' "$meta" | cut -d'"' -f4)
      sha=$(curl -fsSL --max-time 60 \
            "${url%/releases/latest}/commits/${tag}" 2>/dev/null \
            | grep -m1 '"sha"' | cut -d'"' -f4)
      log "tag ${tag:-unknown} commit ${sha:-unresolved}"
      log "sha256 $(sha256sum "$meta" | cut -d' ' -f1)"
      obtained+=("$id")
    else
      log "FAILED (no network, or rate-limited)"
      missed+=("$id|no_network")
    fi
    continue
  fi

  # LEGO-hosted: the artifact usually sits behind a chooser or a login, so
  # record the landing page and flag it for a manual fetch rather than guess a
  # path that may 404 without saying so.
  page="$DEST/${id}.landing.html"
  if curl -fsSL --max-time 60 -A "Mozilla/5.0" "$url" -o "$page" 2>/dev/null; then
    log "landing page saved, sha256 $(sha256sum "$page" | cut -d' ' -f1)"
    log "MANUAL: download the artifact from this page, then"
    log "        tools/archive_toolchains.sh --record-only <file> $id"
    missed+=("$id|manual_only")
  else
    log "FAILED to reach $url"
    missed+=("$id|no_network")
  fi
done

{
  echo '{'
  echo "  \"schema_version\": 1,"
  echo "  \"archived_at\": \"$TODAY\","
  echo "  \"note\": \"NEEDS-VERIFY(ev3-download-window): 31 July 2026 cutoff is third-party, unconfirmed by LEGO\","
  echo "  \"obtained\": [$(printf '"%s",' "${obtained[@]}" | sed 's/,$//')],"
  echo "  \"not_obtained\": [$(printf '"%s",' "${missed[@]}" | sed 's/,$//')]"
  echo '}'
} > "$MANIFEST"

echo
echo "obtained    : ${#obtained[@]}"
echo "NOT obtained: ${#missed[@]}   <- this list is the deliverable"
for m in "${missed[@]}"; do echo "    ${m%%|*}  (${m##*|})"; done
echo
echo "manifest: $MANIFEST"
echo "Copy the summary into docs/TOOLCHAIN_ARCHIVE.md under a dated heading."
