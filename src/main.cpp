// lswtcs: LEGO Star Wars: The Complete Saga, natively.
//
//   lswtcs [--game-dir DIR] [--exe FILE] [-- GAME ARGS...]
//
// DIR is the game install (the folder with GAME.DAT). Defaults to
// $LSWTCS_GAME_DIR. FILE is the unpacked LEGOStarWarsSaga.exe
// (tools/unpack_steamstub.py); defaults to $LSWTCS_EXE. Arguments after
// `--` go on the game's command line. Set LSWTCS_TRACE=1 to log every HLE
// call.

#include <sys/stat.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

#include "runtime/log.h"
#include "runtime/runtime.h"

int main(int argc, char** argv) {
  std::string game_dir, exe, game_args;
  if (const char* e = std::getenv("LSWTCS_GAME_DIR")) game_dir = e;
  if (const char* e = std::getenv("LSWTCS_EXE")) exe = e;
  for (int i = 1; i < argc; i++) {
    if (!std::strcmp(argv[i], "--game-dir") && i + 1 < argc) {
      game_dir = argv[++i];
    } else if (!std::strcmp(argv[i], "--exe") && i + 1 < argc) {
      exe = argv[++i];
    } else if (!std::strcmp(argv[i], "--")) {
      for (i++; i < argc; i++) {
        if (!game_args.empty()) game_args += ' ';
        // Quoted, as on a Windows command line, so an argument with spaces
        // stays one.
        bool quote = std::strpbrk(argv[i], " \t");
        if (quote) game_args += '"';
        game_args += argv[i];
        if (quote) game_args += '"';
      }
    } else {
      std::fprintf(stderr,
                   "usage: %s [--game-dir DIR] [--exe FILE] [-- GAME ARGS...]\n",
                   argv[0]);
      return 2;
    }
  }
  if (game_dir.empty() || exe.empty()) {
    std::fprintf(stderr, "lswtcs: pass --game-dir and --exe (or set "
                         "LSWTCS_GAME_DIR and LSWTCS_EXE)\n");
    return 2;
  }
  while (game_dir.size() > 1 && game_dir.back() == '/') game_dir.pop_back();
  if (const char* t = std::getenv("LSWTCS_TRACE")) recomp::g_trace = *t && *t != '0';

  struct stat st;
  for (const std::string& f : {exe, game_dir + "/GAME.DAT"})
    if (stat(f.c_str(), &st) != 0) {
      std::fprintf(stderr, "lswtcs: %s not found\n", f.c_str());
      return 2;
    }

  recomp::GameConfig game;
  game.id = "lswtcs";
  game.guest_dir = "C:\\Program Files\\LEGO Star Wars Saga";
  game.exe_name = "LEGOStarWarsSaga.exe";
  return recomp::RunProcess(game, exe, game_dir, game_args);
}
