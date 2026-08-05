cmake_minimum_required(VERSION 3.25)

project(CodexLBNative VERSION 1.23.0 LANGUAGES CXX RC)

if(NOT WIN32)
  message(FATAL_ERROR "The XA Codex LB desktop host targets Windows only.")
endif()

if(NOT DEFINED WEBVIEW2_SDK_ROOT)
  message(FATAL_ERROR "WEBVIEW2_SDK_ROOT must point to an extracted Microsoft.Web.WebView2 NuGet package.")
endif()

set(WEBVIEW2_INCLUDE_DIR "${WEBVIEW2_SDK_ROOT}/build/native/include")
set(WEBVIEW2_STATIC_LOADER "${WEBVIEW2_SDK_ROOT}/build/native/x64/WebView2LoaderStatic.lib")
if(NOT EXISTS "${WEBVIEW2_INCLUDE_DIR}/WebView2.h")
  message(FATAL_ERROR "WebView2.h was not found under ${WEBVIEW2_INCLUDE_DIR}")
endif()
if(NOT EXISTS "${WEBVIEW2_STATIC_LOADER}")
  message(FATAL_ERROR "The x64 static WebView2 loader was not found: ${WEBVIEW2_STATIC_LOADER}")
endif()

add_executable(codex_lb_native WIN32
  src/main.cpp
  resources/codex-lb.rc
  resources/app.manifest
)

set_target_properties(codex_lb_native PROPERTIES
  OUTPUT_NAME "Codex LB"
  CXX_STANDARD 17
  CXX_STANDARD_REQUIRED YES
  CXX_EXTENSIONS NO
  MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
)

target_compile_definitions(codex_lb_native PRIVATE
  UNICODE
  _UNICODE
  WIN32_LEAN_AND_MEAN
  NOMINMAX
  CODEX_LB_NATIVE_VERSION=L"1.23.0-beta.2"
)

target_include_directories(codex_lb_native PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}/include"
  "${CMAKE_CURRENT_SOURCE_DIR}/resources"
  "${WEBVIEW2_INCLUDE_DIR}"
)

target_compile_options(codex_lb_native PRIVATE
  $<$<CXX_COMPILER_ID:MSVC>:/W4 /permissive- /EHsc /utf-8>
)

target_link_libraries(codex_lb_native PRIVATE
  "${WEBVIEW2_STATIC_LOADER}"
  advapi32
  comctl32
  ole32
  shell32
  shlwapi
  user32
  winhttp
  ws2_32
)
