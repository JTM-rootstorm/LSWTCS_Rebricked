# LSWTCS

A native port of **LEGO Star Wars: The Complete Saga** (PC, 2009) to
64-bit Linux and macOS on Apple Silicon (Metal). Goals beyond running
natively: widescreen at any resolution and aspect ratio, and an uncapped
frame rate as an option.

There is no emulator, interpreter or Wine involved, and no game code or
data in this repository: you need your own copy of the game, and the
build reads it from where you installed it.

## Status

Groundwork. Nothing is playable yet. The Steam EXE unpacks, its code is
lifted and starts natively: the C runtime and WinMain run up to the
first Windows function not yet reimplemented. Direct3D 9 and the rest of
the game's DirectX layer come next. [FINDINGS.md](FINDINGS.md) tracks
progress and [ARCHITECTURE.md](ARCHITECTURE.md) the plan.

Developed against the Steam release (app 32440). Other releases need
their own lifter manifests.

## How it works

The port is built on [x86recomp](https://github.com/JTM-rootstorm/x86recomp),
the static-recompilation library behind
[DS1-Rebuilt](https://github.com/JTM-rootstorm/DS1-Rebuilt) (Dungeon
Siege) and [CoD1-Reissued](https://github.com/JTM-rootstorm/CoD1-Reissued)
(Call of Duty):

- The game's 32-bit x86 code (`LEGOStarWarsSaga.exe`) is translated
  ahead of time into C++, with exact integer, x87 and SSE semantics, and
  linked with a runtime that reimplements the Windows APIs the game uses
  (Direct3D 9, DirectSound, DirectInput, XInput and Bink are to come).
- That recompiled code is scaffolding. The aim is native source: lifted
  functions are replaced by hand-written C++ one subsystem at a time,
  each checked against the exact lifted version, until nothing lifted is
  left.
- Graphics go through x86recomp's backend-neutral device on SDL_GPU:
  Vulkan on Linux, Metal on macOS.

This repository holds what is specific to this game: the Steam DRM
unpacker, the game configuration, the lifter manifest, (later) the
native replacements, and the docs.

## What you need

- LEGO Star Wars: The Complete Saga, the Steam release. Assets stay
  where Steam put them.
- Linux x86-64 with a Vulkan driver, or macOS on Apple Silicon.
- Clang and LLVM (22 used; the static `libLLVMDemangle.a` and headers),
  CMake 3.25 or newer, Ninja, Python 3, SDL3 and ffmpeg development
  packages, and glslang (`glslangValidator`, for the shaders).
- Ghidra (12.1 used), headless, to find the game's functions.
- A checkout of [x86recomp](https://github.com/JTM-rootstorm/x86recomp)
  next to this one's parent folder (`../../x86recomp`), or pass
  `-DX86RECOMP_DIR=`.

## Building

```sh
G="$HOME/.local/share/Steam/steamapps/common/Lego Star Wars Saga"

# 1. Unpack the Steam EXE (static; nothing from the game is executed).
python3 -I tools/unpack_steamstub.py "$G/LEGOStarWarsSaga.exe" -o unpacked/LEGOStarWarsSaga.exe

# 2. Build the lifter and runtime.
cmake --preset release && cmake --build --preset release

# 3. Find the functions: import into Ghidra, analyse, export.
bash /usr/share/ghidra/support/analyzeHeadless "$PWD" lswtcs_recomp -import unpacked/LEGOStarWarsSaga.exe
python3 -I ../../x86recomp/tools/pe_symbols.py unpacked/LEGOStarWarsSaga.exe --out symbols/LEGOStarWarsSaga
bash /usr/share/ghidra/support/analyzeHeadless "$PWD" lswtcs_recomp -process LEGOStarWarsSaga.exe -noanalysis -readOnly \
  -scriptPath ../../x86recomp/tools/ghidra \
  -postScript ExportFunctions.java symbols/LEGOStarWarsSaga/functions.tsv \
  -postScript ExportJumpTables.java symbols/LEGOStarWarsSaga/jumptables.tsv

# 4. Lift, then build the game.
out/build/release/x86recomp/tools/lifter/recomp_lift --exe unpacked/LEGOStarWarsSaga.exe \
  --symbols symbols/LEGOStarWarsSaga --manifest manifest/LEGOStarWarsSaga.manifest --out generated
cmake --preset release && cmake --build --preset release

# 5. Run.
out/build/release/lswtcs --game-dir "$G" --exe unpacked/LEGOStarWarsSaga.exe
```

## Licence

MIT (see [LICENSE](LICENSE)). LEGO Star Wars: The Complete Saga is ©
LucasArts/Lucasfilm and TT Games; none of its code or data is part of
this repository.
