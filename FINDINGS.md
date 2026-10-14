# Findings

## Status (2026-10-14)
Groundwork. The Steam EXE unpacks statically, Ghidra has analysed it,
the lifter turns it into C++, and the game builds and links against
x86recomp (with two lifter fixes on x86recomp branch `jumptable-dups`,
not merged yet). The CRT start-up runs and WinMain starts; it stops at
the first import without a handler, ole32!CoInitialize (see "First
run"). The game's platform layer (Direct3D 9, D3DX 9, DirectSound 8,
DirectInput 8, XInput) is all still missing from the runtime. Next steps
are under "Next" at the end.

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
| ole32 / OLEAUT32 | 5 / 2 | COM init, `CoCreateInstance`, `CoSetProxyBlanket`, `SysAllocString`/`SysFreeString` (WMI, by the look of it the DirectX SDK's "is this an XInput device" check; to confirm) |
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
2D placement, not adding it from nothing. Registry: the EXE builds
`SOFTWARE\<company>\<title>` and reads a DWORD `LanguageVal` (the Steam
install script writes HKLM\Software\LucasArts\LEGOStarWarsSaga with
PathVal, SilentVal and LanguageVal). GameConfig::registry only seeds
strings; nothing is seeded yet. Check with LSWTCS_TRACE what the game
reads and what it does without it.

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

## First run (2026-10-14, x86recomp jumptable-dups ac3ff08)
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

## Next
1. Merge the lifter fixes (x86recomp `jumptable-dups`) after the
   oracle tests run (DS1/CoD1 ctest with their game EXEs set).
2. The Win32 pieces up to `Direct3DCreate9` (COM init, the WMI device
   check, SHGetFolderPathA for the save/config folder, window class),
   in x86recomp.
3. Decide the HLSL path (ARCHITECTURE.md, "Open decisions") before
   starting the D3D9 HLE.
4. x86recomp HLE, in the order the game needs it: d3d9 (device, resources,
   fixed function where used, vs/ps 1.1-3.0 bytecode to SPIR-V/MSL over
   gfx::Device), d3dx9_35 (shader compile, textures from DDS/TGA in
   memory, fonts, matrix helpers), DirectSound 8 (secondary buffers, 3D?),
   DirectInput 8 keyboard/mouse, XInput on SDL gamepads, Bink with
   DirectSound audio.
5. Then the enhancements: arbitrary aspect ratios, uncapped frame rate
   (after tracing the clock above), resolution list.
