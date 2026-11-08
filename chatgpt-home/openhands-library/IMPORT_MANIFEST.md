# OpenHands Library Mirror — Import Manifest

- Source: https://github.com/madnessgate44-debug/Openhands
- Source branch: `main`
- Source tree SHA: `ea9f6151e2d1524d8413b1b7994556a7f5495929`
- Imported into: `madnessgate44-debug/Blind-sniper-/chatgpt-home/openhands-library/`
- Import date: 2026-11-08
- Imported source files: 68
- Source content: copied without intentional edits; source paths are preserved below this directory.
- Use mode: reference mirror for Blind Sniper; not an installation of the OpenHands runtime.

## Included
- `.agents/.plugin/` marketplace manifest
- `.agents/plugin.json` plugin manifest
- All `.agents/skills/` skill and path-rule files
- All `.agents/dev.openhands/agents/` specialist profiles
- All `.agents/dev.openhands/hooks/` hook definitions and scripts
- Root `AGENTS.md` and `README.md`
- `docs/LOOP.md`, `docs/BACKLOG.md`, `docs/STATUS.md`
- `scripts/validate.py`, `scripts/loader_smoke.py`
- `tests/hooks_test.sh`
- `.github/workflows/validate.yml`

## Limitations
The copied hook scripts, plugin manifests, CI workflow and OpenHands-specific SDK loader are source artifacts only. They do not execute inside ChatGPT. The adapted conversation operating procedure is documented in `../BLIND_SNIPER_OS.md`.

## Integrity
Each source file was fetched from the OpenHands `main` branch through the connected GitHub integration and inserted into the Blind Sniper repository tree. This manifest records the source tree SHA; it does not claim that the mirrored OpenHands validation suite was executed in the Blind Sniper repository.
