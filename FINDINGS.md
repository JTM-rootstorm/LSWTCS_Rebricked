# Findings

## Status (2026-10-14)
The Steam EXE unpacks statically, is lifted, and runs natively on
x86recomp (branch `d3d9`, ahead of main by DirectSound, XInput, WinMM
timers and StretchRect). The game boots through its D3D9 setup, sound
(DirectSound 3D), input and timers, and renders its first screens: the
legal screen and "A long time ago..." are drawn through shaders
translated from its HLSL (about 1,100 draws, 900 frames). It stops at the
first draw with one of its 29 precompiled shaders (D3D9 bytecode, not
HLSL). Still missing: a bytecode translator, Bink with DirectSound.
Next steps are under "Next" at the end.

## The game
- Steam app 32440, build 1017673. One EXE, `LEGOStarWarsSaga.exe`
  (5,472,256 bytes, SHA-256 085688e7...c671), timestamp 0x4AC4A20B
  (2009-10-01). PDB path in the debug directory:
  `d:\Projects\LEGOSagaPC\saga\PC_Release\LEGOStarWarsSaga.pdb`.
- Compiler: MSVC 8 (2005) CRT: `__security_init_cookie` +
  `__tmainCRTStartup` at the entry, `__except_handler4`/`__SEH_prolog4`,
  C++ exceptions (`_CxxThrowException`, `__CxxFrameHandler3`). Fixed base
  0x400000, no relocations, no TLS directory. `.data` is 0x21BBC88
  bytes virtual (35 MB, almost all BSS).
- Data: GAME.DAT plus EPISODE_I..VI.DAT (TT's archive format, ~4.3 GB in
  all), Audio/ (OGG streams, AUDIO.CFG, MUSIC.CFG), Movies/ (Bink). The
  EXE opens the DATs itself; no extraction is needed for the port.
- Bink: the game ships binkw32.dll (SHA-256 feeb17a6...0118); the EXE
  imports 12 functions from it, including `BinkOpenDirectSound` and
  `BinkSetSoundSystem` (Bink audio through DirectSound, not Miles).
  x86recomp's Bink HLE covers 10 entry points, not the same set, and its
  audio goes through Miles.

### Imports (198)
| DLL | n | |
|---|---|---|
| KERNEL32 | 121 | |
| USER32 | 25 | window, message loop, cursor, `LoadKeyboardLayoutA`, `MapVirtualKeyExA` |
| d3d9 | 3 | `Direct3DCreate9`, `D3DPERF_Begin/EndEvent` |
| d3dx9_35 | 14 | `D3DXCompileShader`, `D3DXCreateEffect`, `D3DXCreateEffectFromFileA`, `D3DXCreateEffectCompiler`, `D3DXCreateTextureFromFileInMemory[Ex]`, `D3DXCreateCubeTextureFromFileInMemory`, `D3DXCreateFontA`, `D3DXCreateRenderToSurface`, `D3DXSaveSurfaceToFileInMemory`, `D3DXCreateBuffer`, 3 matrix helpers |
| binkw32 | 12 | see above |
| WINMM | 3 | `timeSetEvent`, `timeKillEvent`, `timeGetTime` |
| DSOUND | 1 | ordinal 11 (`DirectSoundCreate8`) |
| DINPUT8 | 1 | `DirectInput8Create` |
| XINPUT1_3 | 3 | ordinals 2, 3, 4 (`XInputGetState`, `XInputSetState`, `XInputGetCapabilities`) |
| ole32 / OLEAUT32 | 5 / 2 | COM init, `CoCreateInstance`, `CoSetProxyBlanket`, `SysAllocString`/`SysFreeString`: the DirectX SDK's IsXInputDevice (WMI) and Game Explorer VerifyAccess, see "To Direct3DCreate9" |
| ADVAPI32 / SHELL32 / GDI32 | 3 / 3 / 1 | registry read, `SHGetFolderPathA`, `SHCreateDirectoryExA`, `ShellExecuteA` |

### Shaders: HLSL generated at run time
The renderer builds HLSL source at run time and compiles it with
`D3DXCompileShader`: RTTI names `ShaderManagerHLSL`,
`HLSLShaderBuilder`, `ShaderBuilderGen`; the EXE holds the HLSL
fragments (`#if PIXEL_SHADER_VERSION == 20`, `BUILD_VERTEX_SHADER`,
skinning variants, "lego fresnel", parallax, ...). Profiles named in the
EXE: vs_1_1, vs_2_0, vs_2_a, vs_3_0, ps_1_1, ps_2_0, ps_2_a, ps_3_0;
`ForceShaderModel` in pcconfig.txt picks among them. The effect
framework is imported too; whether it is used beyond a corner case is
not known yet. This is the main open design question (ARCHITECTURE.md).

### Settings: pcconfig.txt
Written by the game (format `Name<spaces>%d`): FileVersion, ScreenWidth,
ScreenHeight, WindowWidth/Height/Left/Top, ScreenRefreshRate, FSAA,
Widescreen, volumes, MouseSensitivity, InvertY, Vibration, Bloom/
Shadow/SpeedBlur methods, UseHires, ForceShaderModel. There is a
Widescreen option already (strings "%s: 16:9" / "%s: 4:3"), so
widescreen work is about arbitrary aspect ratios (21:9, 16:10), FOV and
2D placement, not adding it from nothing. Where it lives and the
registry: see "To Direct3DCreate9".

### Timing (first look, not yet traced)
- 0x4FFBB0 reads QueryPerformanceFrequency/Counter once with the process
  pinned to CPU 0 (SetProcessAffinityMask 1, then restored); 0x4FFB20
  returns QPC ticks since then. Probably the game clock.
- 0x631360 is a microsecond sleep accumulator: adds the requested time,
  Sleeps whole milliseconds once over 1 ms and carries the measured
  error. A frame limiter candidate.
- 0x6998A0 starts a 500 ms periodic multimedia timer (timeSetEvent,
  TIME_PERIODIC | TIME_CALLBACK_FUNCTION) with a callback from its
  object; purpose unknown.
- 4 CreateThread sites (0x4FEF70, 0x697E41, 0x69A127, 0x740A9A).
Whether game logic is tied to the frame rate (the console versions run
at 30 or 60) is the key question for an uncapped frame rate.

## First run (2026-10-14, x86recomp jumptable-dups, then 6496f03)
`lswtcs` links (recomp_gfx directly, since there is no D3D9 module to
bring it yet; recomp_mss32 for the Bink HLE). Run with LSWTCS_TRACE=1,
LSWTCS_BACKGROUND=1 and an isolated XDG_DATA_HOME, under a 6 GB cap:
- The MSVC 8 CRT start-up runs (TLS, heap, locale, critical sections,
  GetProcAddress of 32 optional functions) and calls WinMain (0x6DE0E0,
  probe: hInstance 0x400000, nShowCmd 10).
- WinMain calls GetModuleFileNameA, then 0x6DD160 calls
  ole32!CoInitialize (return address 0x6DD18C): fatal, no handler.
- 58 of the 198 imports have no handler: binkw32 6 (BinkCopyToBufferRect,
  BinkGetRealtime, BinkGoto, BinkOpenDirectSound, BinkSetSoundTrack@8,
  BinkSetVolume), d3d9 3, d3dx9_35 14, dinput8 1, dsound 1, xinput1_3 3,
  winmm 2 (timeSetEvent, timeKillEvent), ole32 2 (CoInitialize,
  CoSetProxyBlanket), oleaut32 2, shell32 3 (SHGetFolderPathA,
  SHCreateDirectoryExA, ShellExecuteA), user32 3 (RegisterClassExA,
  LoadKeyboardLayoutA, MapVirtualKeyExA) and kernel32 18 (CompareStringA/W,
  GetFileAttributesExA, SetFilePointerEx, Get/SetProcessAffinityMask,
  SetThreadAffinityMask, SetThreadPriority, VerifyVersionInfoA,
  VerSetConditionMask, GetUserGeoID, OutputDebugStringW, FatalAppExitA,
  console functions). Some of these may never be called.

## To Direct3DCreate9 (2026-10-14, x86recomp win32-startup, then bcc1aa9)
Run with LSWTCS_TRACE=1, LSWTCS_BACKGROUND=1, SDL_ASSERT=abort and an
isolated XDG_DATA_HOME under the 6 GB cap: 1,623 HLE calls, then
`FATAL: unimplemented import d3d9.dll!Direct3DCreate9 called (return
address 006E2BAD)`. After GetModuleFileNameA the game only needed
CoInitialize and SetThreadAffinityMask. Startup order (WinMain 0x6DE0E0):
1. 0x6DD160: CoInitialize, CoCreateInstance(CLSID_GameExplorer
   {9A5EA990-3034-4D6F-9128-01F3C61022BC}, IID_IGameExplorer), then
   IGameExplorer::VerifyAccess on the EXE path (vtable +0x18). If the
   class cannot be created the check passes; only a VerifyAccess failure
   shows "You do not have sufficient permissions to play this game."
   x86recomp's CoCreateInstance returns REGDB_E_CLASSNOTREG (no Game
   Explorer, as on XP), so it passes.
2. SetThreadAffinityMask(GetCurrentThread(), 1): the main thread is
   pinned to CPU 0 for the rest of the run (the clock at 0x4FFBB0 also
   pins the process while it reads QPC). x86recomp keeps the masks as
   bookkeeping and pins nothing on the host.
3. 0x492B40 (the game's main), 0x4011E0: reads the language
   (0x6DC890, key from the EXE: `HKLM\SOFTWARE\LUCASARTS\LEGOSTARWARSSAGA`,
   DWORD `LanguageVal`, 4 bytes). Not found here, so it falls back to
   GetUserDefaultLangID (0x409); 0x409 then becomes 0x809 (UK English)
   because tag 0x4F of the init list (below) is not passed, so the game
   picks language index 1. GetUserGeoID is behind a flag nothing sets.
   A seeded LanguageVal would need a REG_DWORD (GameConfig::registry
   seeds REG_SZ only); not needed for English.
4. 0x6DBB30 (pcapi.cpp, platform init) takes a tag list from 0x4014xx:
   tag 0x2E window title "LEGO® Star Wars™: The Complete Saga", 0x2F
   registry key, 0x30 "LucasArts", 0x31 "LEGO Star Wars - The Complete
   Saga". 0x6DDD50 stores 0x30/0x31 as the save-folder company and title
   with "use My Documents" = 0. It then calls 0x6E2BA0, which creates the
   D3D9 object (before any window; the window class and keyboard-layout
   calls come later), then 0x6DB940 (pcconfig.txt) and 0x6DB990.
- Save/config folder (0x6DD8C0, 0x6DD9E0, statically): SHGetFolderPathA
  (CSIDL_LOCAL_APPDATA, CSIDL_PERSONAL if the flag were set) +
  `\LucasArts\LEGO Star Wars - The Complete Saga\`, created with
  SHCreateDirectoryExA when GetFileAttributesA fails; pcconfig.txt is
  opened there with fopen. With x86recomp's folders that is
  `$XDG_DATA_HOME/lswtcs/drive_c/Documents and Settings/Player/Local
  Settings/Application Data/LucasArts/LEGO Star Wars - The Complete
  Saga/pcconfig.txt`. shell32 SHGetFolderPathA and SHCreateDirectoryExA
  were added for it but are not exercised until Direct3DCreate9 returns.
- WMI (0x6D5080, not reached yet): CoCreateInstance(CLSID_WbemLocator,
  IID_IWbemLocator), ConnectServer `\\.\root\cimv2`,
  CoSetProxyBlanket, ExecQuery over `Win32_PNPEntity` reading
  `DeviceID` and looking for "IG_" plus VID_/PID_: the DirectX SDK's
  IsXInputDevice, used to skip XInput pads in DirectInput enumeration.
  Without the WMI class every device counts as "not XInput", so
  CoSetProxyBlanket and SysAllocString/SysFreeString stay unreached.
- Allocations so far: a 64 MB pool (pcapi.cpp) and a 150 MB heap block
  (0x960003B bytes) before Direct3DCreate9.
- Not reached yet, so still without handlers: RegisterClassExA,
  LoadKeyboardLayoutA, MapVirtualKeyExA, SetThreadPriority,
  VerifyVersionInfoA/VerSetConditionMask, CompareStringA/W,
  GetUserGeoID, the rest of the kernel32 list in "First run".

## D3D9 bring-up (2026-10-14, x86recomp d3d9 c6b4334)
Build: `cmake --preset release -B out/build/release-d3d9
-DX86RECOMP_DIR=../../x86recomp-d3d9` (the game links recomp_d3d9 and
recomp_dinput8). Run as in CLAUDE.md with that binary.
- D3D9 object (0x6E2BA0, before any window): GetDeviceCaps(HAL),
  GetAdapterIdentifier, GetAdapterDisplayMode. The desktop's aspect
  (width / height) is stored right after (0x6E1D00 classifies it): the
  starting point for widescreen.
- Device setup (0x6E3940): GetAdapterModeCount/EnumAdapterModes
  (X8R8G8B8, 16 modes), GetDeviceCaps, CheckDeviceType, multisample
  probes (none, 2, 4, 8, 16 for A8R8G8B8 and D24S8), then CreateDevice:
  1024x768 A8R8G8B8, 2 back buffers, full screen (pcconfig defaults),
  D24S8 auto depth, interval ONE, behaviour 0x54 (hardware vertex
  processing, pure device, multithreaded), no FPU_PRESERVE: the main
  thread's x87 goes to single precision (CW 027F -> 007F), as on
  Windows.
- Then: GetBackBuffer, GetDepthStencilSurface, two 1024x768 A8R8G8B8
  render-target textures and a 1024x768 R32F one (created without
  CheckDeviceFormat; null was dereferenced when it failed), vertex and
  index buffers, three vertex declarations, SetRenderTarget/Clear/Present
  (the first frame), 24 sampler states, ShowCursor(FALSE).
- DirectInput (0x6DACB0): mouse (GUID_SysMouse, exclusive|foreground,
  c_dfDIMouse, DIPROP_AXISMODE absolute, DIPROP_BUFFERSIZE 16), then
  EnumDevices for keyboard (3), pointer (2) and game controllers (4).
  The callback (0x6D9DF0) skips XInput devices (WMI check 0x6D5080),
  opens a keyboard (non-exclusive|foreground|no-win-key, c_dfDIKeyboard)
  and DirectInput joysticks/gamepads (types 0x14/0x15; "Saitek
  P2600/P2900" get a button-count fix). XInput pads are found by
  0x6DA200 polling XInputGetCapabilities for users 0-3 and read with
  XInputGetState (0x6D74E0), so x86recomp's DirectInput reports no
  game controllers and pads go through XInput.
- The CRT's SSE2 math (0x6F6xxx-0x6FDxxx, chosen because the CPU has
  SSE2) and the engine's SSE vector code (0x5B3060-0x5CD500: rsqrtps,
  4x4 transposes) needed SSE forms the lifter lacked; now lifted, and
  the oracle tests over this EXE pass: lift_x87, lift_int, lift_sse (550
  forms). RSQRTPS is the correctly rounded 1/sqrt (x86recomp sse.h).
- Unimplemented sites are 1,000 (the earlier count of 1,044 missed
  every address written with an uppercase hex digit; recounted, all
  remaining ones are data decoded as code: ASCII-shaped addresses and
  pointer tables).
- Asset loading (x86recomp 0ff2f20): two 256x256 DXT3 cube maps with
  one mip level (D3DXCreateCubeTextureFromFileInMemory; D3DX would
  generate the other eight by recompressing, x86recomp keeps one and
  warns) and a 32x32 DXT1 texture with all six levels.
- Stopped at the first D3DXCompileShader (vs_3_0, entry vertexProgram,
  14,522 bytes; return 0x743E6E). See "HLSL".

## HLSL (2026-10-14, first sample)
`LSWTCS_SHADER_DUMP=dir` (x86recomp aaeab97) writes every source
D3DXCompileShader gets. The first one ("Uber Shader v2.0", 646 lines):
- One effect-style file per material, compiled twice: vs_3_0 with entry
  `vertexProgram`, ps_3_0 with `fragmentProgram` (a `technique
  TECHNIQUE_BUILTSHADER` with one pass names both and must be skipped).
- The game's shader builder resolves its own conditionals: only
  object-like `#define`s reach D3DX (the two `#if`s are in comments).
  The EXE's ~1,000 `#if` lines are builder input.
- Globals that are written: `VertexInput vin; VertexOutput vout;
  FragmentOutput fout; half4 fs_layer0_color;` assigned from the entry's
  parameter and read by helper functions. In HLSL non-static globals are
  uniform, so fxc must treat assigned ones as private copies: the
  translator has to as well.
- `uniform` / `shared uniform` constants, many with `: SEMANTIC_X :
  register(cN)` (fixed registers, overlapping by design: worldParams[3]
  and world both at c16, vs_lightParams[11] and vs_sceneAmbientColor at
  c28), others without a register (the compiler places them; the game
  presumably finds them through the constant table, ppConstantTable).
- Types: float4/half4/half3/half, float4x4, half4x4, arrays, structs
  with semantics (POSITION, COLOR0, an array `float4 color[N] :
  COLOR0` for multiple render targets). `iNliNE` (= inline), `const in`
  and `out` parameters, swizzles, `saturate`, `string` globals.
- More samples (pixel shaders with textures and lighting) are needed:
  the run stops at the first compile until the translator returns
  something.

## HLSL translator in the game (2026-10-14, x86recomp branch d3d9)
- Caller (0x743DA0): compiles `vertexProgram` (vs_x) and, when it has a
  pixel source, `fragmentProgram` (ps_x); the profile pair comes from
  the shader model (1_1, 2_0, 2_a, 3_0 strings at 0x7E8B40..78). Flags
  0x200 (D3DXSHADER_AVOID_FLOW_CONTROL), 0x10200 for shader model 1
  (plus D3DXSHADER_USE_LEGACY_D3DX9_31_DLL). No macros, no include
  handler. On failure it logs ppErrorMsgs; on success it creates the
  shaders (device vtable +0x16C CreateVertexShader, through 0x6E4870) and
  hands both constant tables to 0x742410.
- 0x742410 walks a table of semantic names (0x82B1D0.., 0x5C bytes per
  entry: a vertex and a pixel name) and calls only
  ID3DXConstantTable::GetConstantByName and GetConstantDesc. From the
  desc it keeps RegisterIndex, RegisterCount, Elements, the class
  (scalar/vector/matrix) and whether it is a sampler (index + 0x101),
  then sets registers itself. So the table must name the registers the
  translation reads; nothing else of D3DX's table is used.
- The vertex and pixel sources differ (the builder emits per stage): the
  pixel source has its own `register()` bindings.
- With the translator the game compiles three pairs (735, 646 and 651
  lines; one material writes COLOR0-2, i.e. three render targets), all
  six pass glslang, then stops at `SetRenderTarget(1)`. One construct
  was new: `TEXCOORD0_centroid` semantics (centroid interpolation).
- Dumps are now named by profile, entry and source, so the vertex and
  pixel compile of one source no longer overwrite each other.

## Steam DRM: SteamStub 2.1 (2026-10-14)
The entry point (0x2A382ED) is in a `.bind` section and `.text` is
encrypted (entropy 8.0). tools/unpack_steamstub.py replays the loader
statically (nothing executed). What the loader does, from its code:
1. The stub (MSVC debug-style code, `push ebx..ebp; sub esp, 0x1000`)
   copies a 0x364-byte header from 0x2A3A21C and undoes a chained XOR
   (each dword XOR the previous encrypted dword, seeded 0x8FDFCB6D).
   Header: kernel32/user32/shell32 import slots, .bind VA, payload key
   0x366E5C08 at +0x20, payload VA 0x2A8C180 / size 0x1000, the app id
   string "32440", offsets into the payload, and the API names the stub
   resolves itself.
2. If the payload's first dword is not the key, the stub asks
   steam.exe through `Local\SteamStart_SharedMemFile` to fill it in. In
   this release it already matches.
3. Payload: chained XOR from dword 1 with the key. At payload+0xBBC /
   +0xAC8 are the VA (0x2A3A580) and size (0x51C00) of SteamDRMP.dll,
   XTEA-encrypted (32 rounds, 4 keys at payload+0x42C, CBC with IV
   0x55555555 0x55555555). The stub maps it by hand and calls its only
   export, `start(payload, 0x1000)`, then jumps to what it returns.
4. SteamDRMP.dll `start`: debugger checks, compares the EXE on disk with
   its image, checks the Steam client (SteamUtils004,
   STEAMAPPS_INTERFACE_VERSION003, ownership of the app id), then, unless
   flag 4 is set, decrypts the code: payload+0xC34 (32 "stolen" bytes)
   followed by the code section (VA payload+0xA2C = 0x401000, size
   payload+0xD24 = 0x34FFF0) is AES-256 (key payload+0xD28, Crypto++):
   the first block decrypted in ECB is the IV, the rest is CBC with
   PKCS#7 padding, written over the code section. It returns the
   original entry point, payload+0xFA0 = 0x6E74A2. Flags here: 0x20.
- The unpacker writes the PE with the decrypted code, the original entry
  point, checksum 0 and without `.bind` (the last section; nothing points
  into it). The import directory, resources and `.extra` (0x1528 bytes,
  discardable, not referenced by any data directory) are untouched.
  Output: 5,120,000 bytes, SHA-256 5c12d63b...07ef; 3 s. The decrypted
  code was checked against an independent AES implementation
  (pycryptodome) byte for byte.
- Other TT LEGO games on Steam probably use the same wrapper version; the
  payload offsets are those of this SteamDRMP.dll build and every step is
  checked, so a different build fails with a message, not garbage.

## Lift (2026-10-14, x86recomp 0cadefc + branch jumptable-dups)
- Ghidra 12.1.4 auto-analysis: 7,431 functions, 501 jump tables.
- recomp_lift: 13,091 functions (5,660 discovered: 1,614 via code
  pointers, 3,930 via data pointers; 5,538 weak), 28 jump tables
  recovered, 1,207,190 instructions, 100 files (249 MB of C++), 40 s.
- 1,044 unimplemented sites at 161 distinct VAs (in, out, les, daa, arpl,
  cli, "undecodable", ...). The ones inside Ghidra functions are at
  ASCII-shaped addresses (0x657265 "ere", 0x747365 "est", 0x520044,
  ...): weak entries from string bytes read as code pointers, landing
  mid-instruction. Expected to be unreachable; any that is reached is a
  fatal error naming the VA.
- Two lifter bugs this EXE exposed, fixed on x86recomp branch
  `jumptable-dups` (DS1 and CoD1 lifter output byte-identical before and
  after):
  - Recovered jump tables kept repeated targets, which became duplicate
    `case` labels (gen_008, gen_012). Ghidra's tables were already
    deduplicated.
  - FCMOVcc: Zydis files it under the CMOV category, so it was not
    treated as x87 and was emitted as an integer CMOV (invalid C++:
    `(null) = SetLo8(...)`, gen_001). It now takes the exact x87 path
    (`x87::CopySt`) and ends x87 runs. 4 sites, all data decoded as
    code: two at ASCII-shaped addresses (0x410046, 0x4B004D), two in
    pointer tables (0x723148, 0x736CA1). The integer oracle test now skips forms with x87
    register operands; FCMOV has no oracle test (the x87 harness would
    need EFLAGS as an input).
- SEH and C++ exception resume sites are in the manifest
  (`_EH4_TransferToHandler`'s `jmp esi`, `_JumpToContinuation`'s
  `jmp eax`). x86recomp's resume mechanism was built on VC6/VC7's
  `__except_handler3`; VC8's handler4 and C++ catch continuations are
  untested until the game throws.

## Programmable path (2026-10-14, x86recomp branch d3d9)
- With the translated shaders on SDL_GPU (x86recomp fc6b186) the game
  gets through its render-target setup: SetRenderTarget 1-2 (MRT, the
  three-output material), 30 Clears, 7 Presents, 22 vertex and 24 pixel
  shaders created (14 distinct sources so far), 13 vertex buffers, 12
  declarations, no draw yet.
- Two more imports on the way: kernel32 SetThreadPriority (the sound
  thread, priority -2) and D3DXMatrixMultiply (0x5C0514); D3DX's other
  two matrix helpers (LookAtLH, OrthoLH) went in with it.
- Then the sound thread (0x696D26) calls DirectSoundCreate8.

## DirectSound, XInput, timers, first frames (2026-10-14)
- Sound thread setup (0x696CC0): DirectSoundCreate8, SetCooperativeLevel
  (DSSCL_PRIORITY), GetCaps, GetSpeakerConfig, a primary buffer with
  DSBCAPS_CTRL3D set to 44.1 kHz 16-bit stereo, its 3D listener at the
  origin facing +z with rolloff factor 0 (the game attenuates by
  distance itself), all deferred then committed. It then creates and
  fills 155 secondary buffers (Lock/Unlock) before the first frame.
- XInput: the main thread polls XInputGetCapabilities for pads 0-3 every
  frame (0x6DA200).
- A worker (0x6998A0) runs a WinMM timer: timeSetEvent(500 ms,
  resolution 100, TIME_PERIODIC | TIME_CALLBACK_EVENT_PULSE) on an event
  handle, killing the previous one first.
- Render targets: 1024x768 A8R8G8B8, X8R8G8B8 and R32F textures, a
  640x2048 R32F pair, 512x512 targets with mips; StretchRect between
  them (0x6E2347).
- First frames (x86recomp 2ee5f99): legal screen, "A long time ago..."
  fading, correct against the original's look; every draw so far is
  DrawPrimitiveUP with the translated shaders.
- Then the first draw with a precompiled shader. The EXE carries 29
  (seen so far): vs_1_1 x10, vs_2_0 x2, vs_3_0 x2, ps_1_1 x5, ps_2_0 x6,
  ps_3_0 x4 (42-566 tokens). LSWTCS_SHADER_DUMP writes them as .vso/.pso.

## Next
1. A D3D9 shader bytecode translator (shader models 1.1-3.0, to the same
   GLSL contract as the HLSL translator), for the 29 precompiled
   shaders; then on to the menus.
2. More HLSL as the game reaches more materials: check every dump with
   recomp_hlslc + glslang.
3. Bink with DirectSound audio (BinkSoundUseDirectSound).
4. Then the enhancements: arbitrary aspect ratios, uncapped frame rate
   (after tracing the clock), resolution list.
