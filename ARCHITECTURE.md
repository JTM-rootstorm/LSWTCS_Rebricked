# Architecture (draft)

## Goals
- LEGO Star Wars: The Complete Saga (PC, Steam) running natively on
  64-bit Linux and macOS on Apple Silicon (Metal). No Wine, no emulator.
- Widescreen at any resolution and aspect ratio, with the HUD and menus
  placed properly (the game has a 16:9 option; 21:9, 16:10 and others
  are not covered).
- An uncapped frame rate as an option, without changing game speed.
- Keyboard/mouse and gamepads (XInput-style, through SDL).
- The groundwork is meant to carry over to TT's other LEGO games of the
  same engine generation (sibling projects under Travellers_Tales/).

## Recompilation is the scaffold
As with DS1 and CoD1: the EXE is lifted to C++ with x86recomp and run on
its runtime, then replaced subsystem by subsystem with hand-written C++,
each checked against the exact lifted original, until nothing lifted is
left. Lifted code stays exact; scaffold-only mechanisms (guest heap,
thunks, CPUID) stay out of replacement code.

## Decisions (2026-10-14, inherited from the other ports)
- Static recompilation on x86recomp; game knowledge stays in this repo.
- Graphics only through x86recomp's gfx::Device (SDL_GPU: Vulkan on
  Linux, Metal on macOS). No host OpenGL/D3D.
- The Steam EXE is unpacked statically (tools/unpack_steamstub.py); the
  wrapped EXE and SteamDRMP.dll are never run.

## Shape
- x86recomp gains, as generic HLE: Direct3D 9 (this game is its first
  D3D9 user; DS1 is D3D7, CoD1 OpenGL), D3DX 9 (only the functions games
  import), DirectSound 8, DirectInput 8, XInput 1.3, Bink with
  DirectSound audio, WinMM timers.
- This repo: GameConfig (src/main.cpp), the lifter manifest, game hooks
  and replacements (widescreen, frame pacing, ...), the unpacker, docs.

## Open decisions
- **HLSL at run time.** The game generates HLSL source and compiles it
  with D3DXCompileShader (profiles vs/ps 1.1 to 3.0). Something has to
  turn that source into shaders for gfx::Device. Options:
  1. Compile the HLSL to D3D9 bytecode at run time with an HLSL compiler
     library, then translate the bytecode (which the D3D9 HLE needs
     anyway for any precompiled shaders) to SPIR-V/MSL. The candidates
     that accept SM1-3 HLSL: vkd3d-shader (LGPL, Wine project; may
     conflict with "no Wine in the product") or Microsoft's DXC (only
     SM 6 syntax, so the old `tex2D`/`sampler2D` dialect would need
     rewriting).
  2. Capture every generated source string (a finite set: feature bits
     x shader model), compile them offline once with Microsoft's
     compiler on Windows or with any of the above, and ship a cache
     keyed by the source hash. No compiler in the product, but a cache
     made from game-derived text cannot go in git, so it would have to
     be generated on the user's machine.
  3. Port the shader builder: the HLSL fragments become GLSL fragments
     assembled by native code (the end state of the native port anyway).
     The most work up front, the cleanest result.
  To decide with the user once the D3D9 HLE starts; a first trace of
  how many distinct shaders a level produces will help.
- **Frame rate.** Whether game logic is tied to frames (see FINDINGS,
  Timing). Determines whether an uncapped frame rate is a pacing change
  or needs interpolation/fixed steps as in CoD1.

## Milestones (provisional)
- M0: unpacked, lifted, linked. Done 2026-10-14 (pending the lifter fix
  merge).
- M1: CRT and WinMain run to Direct3DCreate9.
- M2: D3D9/D3DX HLE: front-end menus render.
- M3: in-game rendering, input, sound, Bink movies; a level playable.
- M4: macOS arm64 on Metal.
- M5: widescreen at any aspect ratio, uncapped frame rate.
- M6 onward: native replacements, subsystem by subsystem.
