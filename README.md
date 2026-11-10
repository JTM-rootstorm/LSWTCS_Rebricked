# LSWTCS

A native port of **LEGO Star Wars: The Complete Saga** (PC, 2009) to
64-bit Linux and macOS on Apple Silicon (Metal). Goals beyond running
natively: widescreen at any resolution and aspect ratio, and an uncapped
frame rate as an option.

There is no emulator, interpreter or Wine involved, and no game code or
data in this repository: you need your own copy of the game, and the
build reads it from where you installed it.

## Status

In game on Linux. The attract movie, the menus and New Game into the
Mos Eisley cantina work, and levels load and play: Negotiations has
been played through its end tally and on, and the pod race, the
Episode III space battle, Tatooine and the Hoth snowspeeders run.
Keyboard and Xbox pads both work, and every shader the game has used so
far translates.

The frame rate follows the display: the original caps itself at about
85 fps (it only accepts display modes up to 85 Hz), and the port paces
it by the host's refresh rate instead, so a 120 Hz display gets a steady
120 fps.

Known issues:
- Hitches (up to about a second) the first time a new effect or level
  is seen, while its graphics pipelines are built. The driver caches
  them, so later plays are smooth.
- Past the first chapter (the minikit build, the status screen, saving
  and loading, later chapters) is largely untested, and so is sound in
  levels.
- Game speed above 120 fps has not been checked.

On macOS (Apple Silicon, Metal) it builds, passes its tests and runs:
scripted runs show the attract movie, the title screen and the menus,
reach the cantina at 60 fps and load Negotiations, but it has not been
played by hand on the Mac yet.

[FINDINGS.md](FINDINGS.md) tracks progress and next steps, and
[ARCHITECTURE.md](ARCHITECTURE.md) the plan.

Developed against the Steam release (app 32440). Other releases need
their own lifter manifests.

## How it works

The port is built on
[SwARc](https://github.com/JTM-rootstorm/SwARc), a static-recompilation
library shared with other game ports
([project site](https://jtm-rootstorm.github.io/SwARc.site/)):

- The game's 32-bit x86 code (`LEGOStarWarsSaga.exe`) is translated
  ahead of time into C++, with exact integer, x87 and SSE semantics, and
  linked with a runtime that reimplements the Windows APIs the game uses:
  Direct3D 9 and D3DX (its HLSL and compiled shaders translated to
  GLSL), DirectSound, DirectInput, XInput and Bink.
- That recompiled code is scaffolding. The aim is native source: lifted
  functions are replaced by hand-written C++ one subsystem at a time,
  each checked against the exact lifted version, until nothing lifted is
  left.
- Graphics go through SwARc's backend-neutral device on SDL_GPU:
  Vulkan on Linux, Metal on macOS.

This repository holds what is specific to this game: the Steam DRM
unpacker, the game configuration, the lifter manifest, game-side hooks
and patches (`src/`: the level warp and the frame limiter so far), and
the docs.

## What you need

- LEGO Star Wars: The Complete Saga, the Steam release. Assets stay
  where Steam put them.
- Linux x86-64 with a Vulkan driver, or macOS on Apple Silicon.
- Clang and LLVM (22 used; the static `libLLVMDemangle.a` and headers),
  CMake 3.25 or newer, Ninja, Python 3, SDL3 and ffmpeg development
  packages, and glslang (`glslangValidator`, for the shaders).
- Ghidra (12.1 used), headless, to find the game's functions.
- A checkout of SwARc's `main` two folders up (`../../SwARc`, next to
  this repository's parent folder), or pass `-DSWARC_DIR=` to cmake.

## Building

From this repository's folder:

```sh
G="$HOME/.local/share/Steam/steamapps/common/Lego Star Wars Saga"

# 0. SwARc, if you don't have it yet.
git clone https://github.com/JTM-rootstorm/SwARc.git ../../SwARc

# 1. Unpack the Steam EXE (static; nothing from the game is executed).
python3 -I tools/unpack_steamstub.py "$G/LEGOStarWarsSaga.exe" -o unpacked/LEGOStarWarsSaga.exe

# 2. Build the lifter and runtime.
cmake --preset release && cmake --build --preset release

# 3. Find the functions: import into Ghidra, analyse, export.
bash /usr/share/ghidra/support/analyzeHeadless "$PWD" lswtcs_recomp -import unpacked/LEGOStarWarsSaga.exe
python3 -I ../../SwARc/tools/pe_symbols.py unpacked/LEGOStarWarsSaga.exe --out symbols/LEGOStarWarsSaga
bash /usr/share/ghidra/support/analyzeHeadless "$PWD" lswtcs_recomp -process LEGOStarWarsSaga.exe -noanalysis -readOnly \
  -scriptPath ../../SwARc/tools/ghidra \
  -postScript ExportFunctions.java symbols/LEGOStarWarsSaga/functions.tsv \
  -postScript ExportJumpTables.java symbols/LEGOStarWarsSaga/jumptables.tsv

# 4. Lift, then build the game.
out/build/release/swarc/tools/lifter_x86/recomp_lift --exe unpacked/LEGOStarWarsSaga.exe \
  --symbols symbols/LEGOStarWarsSaga --manifest manifest/LEGOStarWarsSaga.manifest --out generated
cmake --preset release && cmake --build --preset release

# 5. Run.
out/build/release/lswtcs --game-dir "$G" --exe unpacked/LEGOStarWarsSaga.exe
```

`unpacked/`, `symbols/`, `generated/` and the Ghidra project are
ignored by git. After updating SwARc, lift again (step 4): the lifted
code follows the library's headers. The `debug` preset works the same
way (`out/build/debug`).

Settings are the game's own (pcconfig.txt, the Options menu). They and
the saves live under `$XDG_DATA_HOME/lswtcs` (by default
`~/.local/share/lswtcs`).

**macOS** (Apple Silicon): SDL_GPU runs on Metal. With Homebrew (`brew
install cmake ninja sdl3 ffmpeg llvm@22 glslang spirv-cross ghidra
openjdk@21`), the steps are the same with these differences: CMake finds
Homebrew's LLVM; `pe_symbols.py` needs `/opt/homebrew/opt/llvm@22/bin`
on `PATH` (for `llvm-undname`); Ghidra's headless script is
`$(brew --prefix ghidra)/libexec/support/analyzeHeadless`, run with
`JAVA_HOME=$(brew --prefix openjdk@21)/libexec/openjdk.jdk/Contents/Home`
(without a terminal it cannot ask for the JDK). Settings and saves live
under `~/Library/Application Support/lswtcs`.

## Tests

`ctest --test-dir out/build/release` runs SwARc's tests (the x87 model
against the host's x87 and its SoftFloat reference, and more). Configure
with `-DLSWTCS_GAME_EXE=unpacked/LEGOStarWarsSaga.exe` to add the
EXE-derived tests: every instruction form in the game, lifted versus
executed natively.

## Useful switches

Environment variables, for testing and debugging:

- `LSWTCS_LEVEL=<name>` makes New Game start that level instead of the
  cantina. The name is a level's file or directory name from the game's
  levels\levels.txt (e.g. `Negotiations_a`); an unknown name logs the
  list.
- `LSWTCS_TRACE=1` logs every Windows API call (`LSWTCS_TRACE_FILTER`
  narrows it).
- `LSWTCS_FULLSCREEN=window|desktop|exclusive` picks how the game's
  fullscreen mode is shown.
- `LSWTCS_FPS_REPORT=<s>` logs the frame rate and the spread of frame
  intervals every s seconds; `LSWTCS_HITCH=<ms>` logs frames longer
  than that.
- `LSWTCS_BACKGROUND=1` keeps the window from taking the keyboard and
  mouse (this also hides pads), for automated runs.
- `LSWTCS_GAME_DIR` and `LSWTCS_EXE` stand in for `--game-dir` and
  `--exe`.

## Legal

LEGO Star Wars: The Complete Saga is © LucasArts/Lucasfilm and TT
Games. This project is not affiliated with or endorsed by them, LEGO or
Valve. It contains no game code, data or assets: the EXE is unpacked
and lifted locally from your own copy, and neither it nor the lifted
code is ever committed.

The code here is under the [MIT License](LICENSE). SwARc and its
dependencies keep their own licences (see SwARc's README): among them
Berkeley SoftFloat 3e (BSD-3-Clause) and Zydis (MIT), fetched at build
time, and SDL3 (zlib), ffmpeg (LGPL, linked dynamically) and LLVM's
demangler (Apache-2.0 with LLVM exception), from your system.
