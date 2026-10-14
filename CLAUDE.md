# LEGO Star Wars: The Complete Saga (PC, 2009) → native Linux/macOS port

Rules only. Status, findings and next steps go in FINDINGS.md; design in
ARCHITECTURE.md. The lifter, x87 model, runtime and HLE are the shared
x86recomp library (../../x86recomp, its own git repo with its own
CLAUDE.md, also used by DS1 and CoD1); this repo holds what is specific
to this game.

## Layout
- Project: ~/Documents/Programming/Recomp/Travellers_Tales/LSWTCS
  (Travellers_Tales/ gets sibling projects for TT's other LEGO games;
  material shared between them, such as reference tools, goes in
  Travellers_Tales/tools_ext)
- Game (Steam, app 32440; NEVER commit or copy into the repo):
  $HOME/.local/share/Steam/steamapps/common/Lego Star Wars Saga/
  (LEGOStarWarsSaga.exe, binkw32.dll, GAME.DAT, EPISODE_*.DAT, Audio/, Movies/)
- Library: ~/Documents/Programming/Recomp/x86recomp
  (github.com/JTM-rootstorm/x86recomp; added with add_subdirectory,
  X86RECOMP_DIR overrides the path). Library changes are committed
  there, its rules apply to them, and DS1 and CoD1 must keep building and
  passing their tests after them.
- Unpacked EXE: unpacked/ (gitignored, regenerate, see below)
- Symbols: symbols/LEGOStarWarsSaga/ (gitignored). Lifter manifest:
  manifest/LEGOStarWarsSaga.manifest
- Ghidra project: lswtcs_recomp.gpr / lswtcs_recomp.rep (gitignored)

## Unpacking
- The Steam LEGOStarWarsSaga.exe is wrapped in SteamStub 2.1 (`.bind`
  section, AES-encrypted code). Analyse and lift the unpacked copy, never
  the wrapped one:
  `python3 -I tools/unpack_steamstub.py "$HOME/.local/share/Steam/steamapps/common/Lego Star Wars Saga/LEGOStarWarsSaga.exe" -o unpacked/LEGOStarWarsSaga.exe`
- The unpacker only replays the wrapper's loader statically. Never run the
  wrapped EXE (or its SteamDRMP.dll) to dump it.

## Build
- `cmake --preset release && cmake --build --preset release` (debug:
  `--preset debug`). Output in out/build/<preset>/.
- Symbols (after any Ghidra change that matters):
  `python3 -I ../../x86recomp/tools/pe_symbols.py unpacked/LEGOStarWarsSaga.exe --out symbols/LEGOStarWarsSaga`
  and `bash /usr/share/ghidra/support/analyzeHeadless "$PWD" lswtcs_recomp -process LEGOStarWarsSaga.exe -noanalysis -readOnly -scriptPath ../../x86recomp/tools/ghidra -postScript ExportFunctions.java symbols/LEGOStarWarsSaga/functions.tsv -postScript ExportJumpTables.java symbols/LEGOStarWarsSaga/jumptables.tsv`
- Lift (then re-run cmake; the generated file list is globbed):
  `out/build/release/x86recomp/tools/lifter/recomp_lift --exe unpacked/LEGOStarWarsSaga.exe --symbols symbols/LEGOStarWarsSaga --manifest manifest/LEGOStarWarsSaga.manifest --out generated`
- Run: `out/build/release/lswtcs --game-dir "$HOME/.local/share/Steam/steamapps/common/Lego Star Wars Saga" --exe unpacked/LEGOStarWarsSaga.exe`
  (LSWTCS_TRACE=1 logs every HLE call; LSWTCS_BACKGROUND=1 for automated
  runs). Automated runs go inside a memory cap:
  `systemd-run --user --scope --quiet -p MemoryMax=6G -p MemorySwapMax=0 <command>`

## Product constraints
x86recomp's (its CLAUDE.md): no emulation or Wine in the product, 64-bit
host only, portable to macOS arm64 + Metal (graphics only through
gfx::Device, never a host graphics API directly), exact x87.

## Rules
- Paths with spaces ("Lego Star Wars Saga"): always quote them in shell
  commands, scripts and CMake.
- No game files, unpacked binaries, SteamDRMP.dll, memory dumps, extracted
  DAT contents, captured shaders, captures or symbol dumps in git.
  Lifted/generated code is gitignored too.
- Game knowledge (paths, registry, engine struct offsets, game patches
  such as widescreen/FOV/frame-rate fixes) goes in src/ here (GameConfig,
  hooks, replacements), never in x86recomp. Generic Direct3D 9, D3DX,
  DirectSound, DirectInput and XInput behaviour belongs in x86recomp.
- x86recomp is shared by several projects and sessions: change it only
  in a git worktree (`git -C ../../x86recomp worktree add
  ../x86recomp-<topic> -b <topic> main`) and build this game against it
  in its own build dir (-DX86RECOMP_DIR=...). Never edit its main
  checkout.
- Ghidra names need evidence (strings, call-graph position, data layout,
  RTTI); record it in a plate comment. A function that merely looks like
  a known one stays unnamed until confirmed.
- Python scripts that read game files run with `python3 -I`.
- /usr/share/ghidra/support/analyzeHeadless has no exec bit: run it as
  `bash /usr/share/ghidra/support/analyzeHeadless ...`.
- Commits: GPG-signed (global config), no Claude co-author trailers or
  generated-by markers.
- Record findings in FINDINGS.md, not here.
