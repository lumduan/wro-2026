# Toolchain archive — do this today

`last_reviewed: 2026-07-27`

**`NEEDS-VERIFY(ev3-download-window)`: third-party sources put the EV3 app download cutoff at
31 July 2026. LEGO's own retired-products page still hosts EV3 Lab and states no removal date.**

The verification status does not change the decision. Archiving costs minutes; missing the window
is permanent, and without an EV3 toolchain `robot/robot_io_ev3.py` can never be verified — which
removes half of B1's answer and with it ADR-023's evidence.

Run `tools/archive_toolchains.sh`. It fetches what it can, records a sha256 for every file, and
**records what it could not get and why** — the second half matters as much as the first.

---

## Priority order — LEGO-hosted first

**LEGO-hosted artifacts are the ones that disappear.** GitHub-hosted ones persist and are pinned
for reproducibility, not for survival.

| # | artifact | host | why first |
|---|---|---|---|
| 1 | **EV3 MicroPython image** (SD-card `.zip`) | LEGO / Pybricks | the EV3 half of `RobotIO` runs on this |
| 2 | **EV3 Lab** installer, Win + macOS | LEGO | retired product page; no stated removal date, no guarantee |
| 3 | **EV3 Classroom** installer, Win + macOS | LEGO | same |
| 4 | **EV3 firmware** image | LEGO | a brick with wrong firmware and no download is a brick |
| 5 | **SPIKE App** installer | LEGO | supported to 2031, but direct sales ended 30 June 2026 |
| 6 | Pybricks release + **commit hash** | GitHub | persists; pin anyway |
| 7 | ev3dev / `ev3dev-lang-python` release + **commit hash** | GitHub | persists; pin anyway |

**Pin GitHub by tag *and* commit.** A tag can be moved or deleted; a commit hash cannot.

---

## Where it goes

`archive/toolchains/` — **gitignored**, for the same reason the source PDFs are: these are LEGO's
binaries, not ours. The repo commits the **manifest**, never the payload.

```
archive/toolchains/
  MANIFEST.json          <- committed? no. generated, and summarised into this file
  ev3/…
  spike/…
  pybricks/…
```

## Manifest schema

```json
{
  "schema_version": 1,
  "archived_at": "2026-07-27",
  "note": "NEEDS-VERIFY(ev3-download-window): 31 July 2026 cutoff is third-party, unconfirmed by LEGO",
  "artifacts": [
    {
      "id": "ev3-micropython-image",
      "host": "lego",
      "url": "…",
      "status": "obtained",
      "bytes": 0,
      "sha256": "…",
      "obtained_at": "2026-07-27T…"
    },
    {
      "id": "ev3-lab-macos",
      "host": "lego",
      "url": "…",
      "status": "not_obtained",
      "reason": "login_required",
      "note": "LEGO account needed; fetch manually and re-run with --record-only"
    },
    {
      "id": "pybricks-micropython",
      "host": "github",
      "release_tag": "v…",
      "commit": "…",
      "status": "obtained",
      "sha256": "…"
    }
  ],
  "not_obtained": ["ev3-lab-macos", "…"]
}
```

**`status` is one of `obtained` · `not_obtained` · `superseded`.** Every `not_obtained` carries a
`reason` from: `login_required` · `http_404` · `no_network` · `manual_only`.

## What the script cannot do

- **Anything behind a LEGO account login.** It records those as `login_required` with the URL, so
  they can be fetched by hand and registered with `--record-only <file>`, which hashes an
  existing file into the manifest without downloading.
- **Judge whether a download is the right version.** It records what it got; you confirm.

## After running

1. Read the `not_obtained` list. **That list is the deliverable** — it says what is still at risk.
2. Fetch anything `login_required` by hand, today.
3. Re-run with `--record-only` for each, so the manifest is complete.
4. Copy the summary into this file under a dated heading, so the repo carries the record even
   though it does not carry the payload.

## Archive log

### 2026-07-27 — first run · **2 obtained, 5 still at risk**

**Obtained — GitHub, pinned by tag *and* commit:**

| artifact | tag | commit |
|---|---|---|
| `pybricks-micropython` | **v4.0.1** | `4104553405decb0384bcfb030fbfcb4b5a9854cc` |
| `ev3dev-lang-python` | **1.0.0** | `55f57ada176905a1db073423f428bd83dfd6b6ca` |

> **⚠ Pybricks v4.0.1 does not cover EV3.** v4 targets SPIKE and the newer hubs; **EV3 needs
> Pybricks v2.x**, distributed as the separate *EV3 MicroPython* SD-card image — which is item 1
> on the manual list below. Pinning "latest" therefore archives the **SPIKE** side and leaves the
> **EV3** side exactly as exposed as before. Do not read "2 obtained" as covering EV3.

**Not obtained — all five are `manual_only`, all five are LEGO-hosted:**

| artifact | landing page reached | sha256 of landing page |
|---|---|---|
| `ev3-micropython-image` | `pybricks.com/ev3-micropython/` | *(saved)* |
| `ev3-lab` | `education.lego.com/…/retiredproducts/` | `08123b91…` |
| `ev3-classroom` | same page | `08123b91…` |
| `ev3-firmware` | same page | `08123b91…` |
| `spike-app` | `education.lego.com/…/spike-app/software/` | `1dbd122e…` |

Three share a hash because they share one retired-products landing page — expected, not an error.

**The landing pages are reachable; the binaries behind them are not scriptable.** Each needs a
chooser click or a LEGO account. **These five are the whole risk**, and item 1 is the one that
decides whether B1 can ever run on EV3.

**Next action — today:** download those five by hand and register each:

```bash
tools/archive_toolchains.sh --record-only <downloaded-file> ev3-micropython-image
```

Start with `ev3-micropython-image`. Everything else is recoverable; that one is not.
