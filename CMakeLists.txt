cmake_minimum_required(VERSION 3.25)
project(lswtcs LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# x86recomp: the lifter, x87 model and runtime (a sibling checkout).
set(X86RECOMP_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../x86recomp"
    CACHE PATH "x86recomp source tree")

enable_testing()
add_subdirectory("${X86RECOMP_DIR}" x86recomp)

# The game: runtime + HLE + lifted code (generated/, produced by
# recomp_lift; see CLAUDE.md for the command).
recomp_add_lifted(lswtcs_lifted "${CMAKE_CURRENT_SOURCE_DIR}/generated")
if(TARGET lswtcs_lifted)
  add_executable(lswtcs src/main.cpp $<TARGET_OBJECTS:lswtcs_lifted>)
  # recomp_mss32 for the Bink HLE's audio.
  target_link_libraries(lswtcs PRIVATE recomp_runtime recomp_mss32 recomp_bink
                        recomp_d3d9 recomp_dinput8 recomp_dsound recomp_xinput)
  set_target_properties(lswtcs PROPERTIES ENABLE_EXPORTS ON)  # symbol names in fault backtraces
endif()

# Oracle tests over every instruction form in the EXE. Configure with
#   -DLSWTCS_GAME_EXE=unpacked/LEGOStarWarsSaga.exe
set(LSWTCS_GAME_EXE "" CACHE FILEPATH "unpacked LEGOStarWarsSaga.exe for EXE-derived tests")
recomp_add_lift_tests(EXE "${LSWTCS_GAME_EXE}"
  SYMBOLS "${CMAKE_CURRENT_SOURCE_DIR}/symbols/LEGOStarWarsSaga"
  MANIFEST "${CMAKE_CURRENT_SOURCE_DIR}/manifest/LEGOStarWarsSaga.manifest")
