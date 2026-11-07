// Game patch: the frame limiter paces by the host display's refresh rate.
// FINDINGS.md "Frame pacing".
//
// The per-frame update (0x4FD050) sleeps until a frame has taken at least
// 1 / max(85, rate) seconds, where rate is the device's
// FullScreen_RefreshRateInHz, returned by 0x6DF270 (its only caller). The
// game keeps only display modes of 40-85 Hz (0x6E42D0), so the rate is at
// most 85 and the limiter holds the game near 85 fps: on a faster display
// with vsync that misses refreshes unevenly. Returning the host's rate
// lets vsync pace the frames there; at 85 Hz or less nothing changes.

#include "runtime/display.h"
#include "x86/lifted.h"

namespace recomp::gen {

void f_006DF270(Ctx& c) {
  c.eax = uint32_t(DesktopRefreshRate());
  c.esp += 4;
}

}  // namespace recomp::gen
