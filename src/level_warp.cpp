// Test hook: LSWTCS_LEVEL=<level> makes New Game start that level instead
// of the cantina, so automated runs reach a level with a few key presses.
// <level> is a record's file name or its directory's last component, as
// in levels\levels.txt (e.g. negotiations); an unknown name lists them.
// FINDINGS.md "Levels and the level warp".
//
// 0x5788F0 parses levels\levels.txt (called once at startup, 0x4CA3EE):
// it returns the table of 0x130-byte records (stored at 0x951B78) and
// writes the count through its fifth argument (0x951B84). It keeps the
// newgame_level record in 0x951B8C, which the New Game handler (0x4950C8)
// copies to the next-level pointer 0x951B80.

#include <strings.h>

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>

#include "runtime/lifted.h"
#include "runtime/log.h"
#include "runtime/runtime.h"

namespace recomp::gen {

namespace {

constexpr uint32_t kRecordSize = 0x130;
constexpr uint32_t kRecordDir = 0x0;    // char[0x40], e.g. levels\...\name
constexpr uint32_t kRecordFile = 0x40;  // file name
constexpr uint32_t kNewGameLevel = 0x951B8C;

std::string Field(uint32_t va, size_t max) {
  const char* s = reinterpret_cast<const char*>(GPtr(va));
  return std::string(s, strnlen(s, max));
}

}  // namespace

void f_005788F0_lifted(Ctx& c);

void f_005788F0(Ctx& c) {
  const uint32_t count_ptr = Rd32(c.esp + 20);
  f_005788F0_lifted(c);
  const char* want = std::getenv("LSWTCS_LEVEL");
  if (!want || !*want) return;
  const uint32_t table = c.eax, count = Rd32(count_ptr);
  std::string names;
  for (uint32_t i = 0; i < count; i++) {
    const uint32_t r = table + i * kRecordSize;
    const std::string dir = Field(r + kRecordDir, 0x40);
    const std::string file = Field(r + kRecordFile, 0x20);
    const size_t slash = dir.find_last_of('\\');
    const std::string leaf = slash == std::string::npos ? dir : dir.substr(slash + 1);
    if (!strcasecmp(want, file.c_str()) || !strcasecmp(want, leaf.c_str())) {
      Wr32(kNewGameLevel, r);
      WarnF("LSWTCS_LEVEL: New Game starts %s (%s)\n", file.c_str(), dir.c_str());
      return;
    }
    names += ' ' + file;
  }
  WarnF("LSWTCS_LEVEL: no level %s; the levels are:%s\n", want, names.c_str());
}

}  // namespace recomp::gen
