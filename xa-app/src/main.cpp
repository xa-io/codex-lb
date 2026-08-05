#include <winsock2.h>
#include <windows.h>
#include <winhttp.h>
#include <shellapi.h>
#include <shlobj.h>
#include <shlwapi.h>
#include <wrl.h>
#include <WebView2.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "resource.h"

using Microsoft::WRL::Callback;
using Microsoft::WRL::ComPtr;
namespace fs = std::filesystem;

namespace {

constexpr wchar_t kWindowClass[] = L"XA.CodexLB.NativeWindow";
constexpr wchar_t kWindowTitle[] = L"Codex LB";
constexpr UINT kMessageBackendReady = WM_APP + 1;
constexpr UINT kMessageBackendError = WM_APP + 2;
constexpr int kDefaultPort = 2455;

struct Options {
    int port = kDefaultPort;
    bool selfTest = false;
    fs::path dataDir;
};

struct HttpResponse {
    bool transportOk = false;
    DWORD status = 0;
    std::string body;
    std::wstring appVersion;
};

struct AppState {
    HINSTANCE instance = nullptr;
    HWND window = nullptr;
    Options options;
    fs::path executableDir;
    fs::path dataDir;
    std::wstring baseUrl;
    std::wstring statusText = L"Preparing the local Codex LB service...";
    std::wstring errorText;
    std::mutex statusMutex;
    std::atomic<bool> closing{false};
    std::atomic<bool> backendReady{false};
    bool backendOwned = false;
    bool backendReused = false;
    HANDLE backendProcess = nullptr;
    HANDLE backendThread = nullptr;
    HANDLE shutdownEvent = nullptr;
    HANDLE backendJob = nullptr;
    std::wstring shutdownEventName;
    std::thread backendWorker;
    ComPtr<ICoreWebView2Controller> webviewController;
    ComPtr<ICoreWebView2> webview;
};

AppState g_app;

std::wstring FormatWin32Error(DWORD code) {
    wchar_t* buffer = nullptr;
    const DWORD count = FormatMessageW(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
        nullptr,
        code,
        0,
        reinterpret_cast<wchar_t*>(&buffer),
        0,
        nullptr);
    std::wstring message = count && buffer ? std::wstring(buffer, count) : L"Unknown Windows error";
    if (buffer) LocalFree(buffer);
    while (!message.empty() && (message.back() == L'\r' || message.back() == L'\n')) message.pop_back();
    return message;
}

std::wstring FormatHResult(HRESULT result) {
    return FormatWin32Error(static_cast<DWORD>(result));
}

std::string WideToUtf8(const std::wstring& value) {
    if (value.empty()) return {};
    const int required = WideCharToMultiByte(
        CP_UTF8, 0, value.c_str(), static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    if (required <= 0) return "Unable to convert the Windows error message.";
    std::string output(static_cast<size_t>(required), '\0');
    WideCharToMultiByte(
        CP_UTF8,
        0,
        value.c_str(),
        static_cast<int>(value.size()),
        output.data(),
        required,
        nullptr,
        nullptr);
    return output;
}

std::wstring LocalTimestamp() {
    SYSTEMTIME value{};
    GetLocalTime(&value);
    std::wostringstream stream;
    stream << std::setfill(L'0') << std::setw(4) << value.wYear << L"-" << std::setw(2) << value.wMonth
           << L"-" << std::setw(2) << value.wDay << L" " << std::setw(2) << value.wHour << L":"
           << std::setw(2) << value.wMinute << L":" << std::setw(2) << value.wSecond;
    return stream.str();
}

std::wstring LogFileDate() {
    SYSTEMTIME value{};
    GetLocalTime(&value);
    std::wostringstream stream;
    stream << std::setfill(L'0') << std::setw(4) << value.wYear << L"-" << std::setw(2) << value.wMonth
           << L"-" << std::setw(2) << value.wDay;
    return stream.str();
}

void AppendLifecycleLog(const std::wstring& message) {
    try {
        const fs::path logDir = g_app.dataDir / L"logs";
        fs::create_directories(logDir);
        const fs::path logPath = logDir / (L"native-" + LogFileDate() + L".log");
        std::wofstream stream(logPath, std::ios::app);
        stream << LocalTimestamp() << L" " << message << L"\n";
    } catch (...) {
        // Logging must never prevent the application from opening or closing.
    }
}

fs::path ModuleDirectory() {
    std::vector<wchar_t> buffer(32768);
    const DWORD length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (length == 0 || length >= buffer.size()) return fs::current_path();
    return fs::path(std::wstring(buffer.data(), length)).parent_path();
}

fs::path DefaultDataDirectory() {
    wchar_t* profile = nullptr;
    size_t count = 0;
    if (_wdupenv_s(&profile, &count, L"USERPROFILE") == 0 && profile && *profile) {
        fs::path result = fs::path(profile) / L".codex-lb";
        free(profile);
        return result;
    }
    if (profile) free(profile);
    PWSTR knownFolder = nullptr;
    if (SUCCEEDED(SHGetKnownFolderPath(FOLDERID_Profile, 0, nullptr, &knownFolder))) {
        fs::path result = fs::path(knownFolder) / L".codex-lb";
        CoTaskMemFree(knownFolder);
        return result;
    }
    return fs::temp_directory_path() / L".codex-lb";
}

bool ParsePort(const std::wstring& raw, int& port) {
    try {
        size_t consumed = 0;
        const int parsed = std::stoi(raw, &consumed);
        if (consumed != raw.size() || parsed < 1 || parsed > 65535) return false;
        port = parsed;
        return true;
    } catch (...) {
        return false;
    }
}

bool ParseOptions(Options& options, std::wstring& error) {
    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (!argv) {
        error = L"Windows could not parse the application command line.";
        return false;
    }
    for (int index = 1; index < argc; ++index) {
        const std::wstring argument = argv[index];
        if (argument == L"--self-test") {
            options.selfTest = true;
        } else if (argument == L"--port" && index + 1 < argc) {
            if (!ParsePort(argv[++index], options.port)) {
                error = L"--port must be an integer between 1 and 65535.";
                LocalFree(argv);
                return false;
            }
        } else if (argument == L"--data-dir" && index + 1 < argc) {
            options.dataDir = fs::path(argv[++index]);
        } else {
            error = L"Unknown or incomplete argument: " + argument;
            LocalFree(argv);
            return false;
        }
    }
    LocalFree(argv);
    return true;
}

std::wstring QuoteArgument(const std::wstring& value) {
    if (value.find_first_of(L" \t\"") == std::wstring::npos) return value;
    std::wstring result = L"\"";
    unsigned backslashes = 0;
    for (const wchar_t character : value) {
        if (character == L'\\') {
            ++backslashes;
        } else if (character == L'\"') {
            result.append(backslashes * 2 + 1, L'\\');
            result.push_back(L'\"');
            backslashes = 0;
        } else {
            result.append(backslashes, L'\\');
            backslashes = 0;
            result.push_back(character);
        }
    }
    result.append(backslashes * 2, L'\\');
    result.push_back(L'\"');
    return result;
}

HttpResponse HttpGet(int port, const std::wstring& path, DWORD timeoutMs = 4000) {
    HttpResponse response;
    HINTERNET session = WinHttpOpen(
        L"Codex-LB-Native/" CODEX_LB_NATIVE_VERSION,
        WINHTTP_ACCESS_TYPE_NO_PROXY,
        WINHTTP_NO_PROXY_NAME,
        WINHTTP_NO_PROXY_BYPASS,
        0);
    if (!session) return response;
    WinHttpSetTimeouts(session, timeoutMs, timeoutMs, timeoutMs, timeoutMs);
    HINTERNET connection = WinHttpConnect(session, L"127.0.0.1", static_cast<INTERNET_PORT>(port), 0);
    if (!connection) {
        WinHttpCloseHandle(session);
        return response;
    }
    HINTERNET request = WinHttpOpenRequest(
        connection,
        L"GET",
        path.c_str(),
        nullptr,
        WINHTTP_NO_REFERER,
        WINHTTP_DEFAULT_ACCEPT_TYPES,
        0);
    if (!request) {
        WinHttpCloseHandle(connection);
        WinHttpCloseHandle(session);
        return response;
    }
    const BOOL sent = WinHttpSendRequest(
        request,
        WINHTTP_NO_ADDITIONAL_HEADERS,
        0,
        WINHTTP_NO_REQUEST_DATA,
        0,
        0,
        0);
    if (sent && WinHttpReceiveResponse(request, nullptr)) {
        response.transportOk = true;
        DWORD statusSize = sizeof(response.status);
        WinHttpQueryHeaders(
            request,
            WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
            WINHTTP_HEADER_NAME_BY_INDEX,
            &response.status,
            &statusSize,
            WINHTTP_NO_HEADER_INDEX);

        DWORD versionSize = 0;
        WinHttpQueryHeaders(
            request,
            WINHTTP_QUERY_CUSTOM,
            L"X-App-Version",
            nullptr,
            &versionSize,
            WINHTTP_NO_HEADER_INDEX);
        if (GetLastError() == ERROR_INSUFFICIENT_BUFFER && versionSize >= sizeof(wchar_t)) {
            std::vector<wchar_t> version(versionSize / sizeof(wchar_t));
            if (WinHttpQueryHeaders(
                    request,
                    WINHTTP_QUERY_CUSTOM,
                    L"X-App-Version",
                    version.data(),
                    &versionSize,
                    WINHTTP_NO_HEADER_INDEX)) {
                response.appVersion.assign(version.data());
            }
        }

        DWORD available = 0;
        while (WinHttpQueryDataAvailable(request, &available) && available > 0) {
            std::string chunk(available, '\0');
            DWORD read = 0;
            if (!WinHttpReadData(request, chunk.data(), available, &read)) break;
            chunk.resize(read);
            response.body += chunk;
            if (response.body.size() > 16 * 1024 * 1024) break;
        }
    }
    WinHttpCloseHandle(request);
    WinHttpCloseHandle(connection);
    WinHttpCloseHandle(session);
    return response;
}

bool IsCodexLbHealthy(int port) {
    const HttpResponse response = HttpGet(port, L"/health");
    return response.transportOk && response.status == 200 && !response.appVersion.empty() &&
           response.body.find("\"status\":\"ok\"") != std::string::npos;
}

bool IsPortListening(int port) {
    SOCKET socketHandle = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (socketHandle == INVALID_SOCKET) return false;
    u_long nonBlocking = 1;
    ioctlsocket(socketHandle, FIONBIO, &nonBlocking);
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(static_cast<u_short>(port));
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    const int connected = connect(socketHandle, reinterpret_cast<sockaddr*>(&address), sizeof(address));
    if (connected == SOCKET_ERROR && WSAGetLastError() == WSAEWOULDBLOCK) {
        fd_set writeSet;
        FD_ZERO(&writeSet);
        FD_SET(socketHandle, &writeSet);
        timeval timeout{0, 250000};
        const int selected = select(0, nullptr, &writeSet, nullptr, &timeout);
        if (selected > 0) {
            int socketError = 0;
            int size = sizeof(socketError);
            getsockopt(socketHandle, SOL_SOCKET, SO_ERROR, reinterpret_cast<char*>(&socketError), &size);
            closesocket(socketHandle);
            return socketError == 0;
        }
    }
    closesocket(socketHandle);
    return connected == 0;
}

void SetStatus(const std::wstring& status) {
    std::lock_guard<std::mutex> guard(g_app.statusMutex);
    g_app.statusText = status;
    if (g_app.window) InvalidateRect(g_app.window, nullptr, TRUE);
}

void SetError(const std::wstring& error) {
    {
        std::lock_guard<std::mutex> guard(g_app.statusMutex);
        g_app.errorText = error;
    }
    AppendLifecycleLog(L"ERROR " + error);
    if (g_app.window) PostMessageW(g_app.window, kMessageBackendError, 0, 0);
}

struct SavedEnvironment {
    std::wstring name;
    bool existed = false;
    std::wstring value;
};

SavedEnvironment SaveEnvironment(const std::wstring& name) {
    SavedEnvironment saved;
    saved.name = name;
    const DWORD required = GetEnvironmentVariableW(name.c_str(), nullptr, 0);
    if (required > 0) {
        std::vector<wchar_t> buffer(required);
        if (GetEnvironmentVariableW(name.c_str(), buffer.data(), required) > 0) {
            saved.existed = true;
            saved.value.assign(buffer.data());
        }
    }
    return saved;
}

void RestoreEnvironment(const std::vector<SavedEnvironment>& saved) {
    for (const auto& entry : saved) {
        SetEnvironmentVariableW(entry.name.c_str(), entry.existed ? entry.value.c_str() : nullptr);
    }
}

bool StartOwnedBackend(std::wstring& error) {
    const fs::path backendPath = g_app.executableDir / L"backend" / L"codex-lb-backend.exe";
    if (!fs::is_regular_file(backendPath)) {
        error = L"The bundled backend is missing:\n" + backendPath.wstring() +
                L"\n\nRebuild the application with xa-app\\build.py.";
        return false;
    }

    const DWORD processId = GetCurrentProcessId();
    const ULONGLONG tick = GetTickCount64();
    g_app.shutdownEventName = L"Local\\XA-CodexLB-Shutdown-" + std::to_wstring(processId) + L"-" +
                              std::to_wstring(tick);
    g_app.shutdownEvent = CreateEventW(nullptr, TRUE, FALSE, g_app.shutdownEventName.c_str());
    if (!g_app.shutdownEvent) {
        error = L"Could not create the backend shutdown signal: " + FormatWin32Error(GetLastError());
        return false;
    }

    std::wstring command = QuoteArgument(backendPath.wstring()) + L" --host 127.0.0.1 --port " +
                           std::to_wstring(g_app.options.port) + L" --shutdown-event " +
                           QuoteArgument(g_app.shutdownEventName);
    std::vector<wchar_t> commandBuffer(command.begin(), command.end());
    commandBuffer.push_back(L'\0');

    std::vector<SavedEnvironment> saved;
    const std::map<std::wstring, std::wstring> childEnvironment = {
        {L"PORT", std::to_wstring(g_app.options.port)},
        {L"CODEX_LB_DATA_DIR", g_app.dataDir.wstring()},
        {L"CODEX_LB_HTTP_RESPONSES_SESSION_BRIDGE_ENABLED", L"false"},
    };
    for (const auto& [name, value] : childEnvironment) {
        saved.push_back(SaveEnvironment(name));
        SetEnvironmentVariableW(name.c_str(), value.c_str());
    }
    if (g_app.options.selfTest) {
        const std::map<std::wstring, std::wstring> testEnvironment = {
            {L"CODEX_LB_AUTH_GUARDIAN_ENABLED", L"false"},
            {L"CODEX_LB_AUTOMATIONS_SCHEDULER_ENABLED", L"false"},
            {L"CODEX_LB_LEADER_ELECTION_ENABLED", L"false"},
            {L"CODEX_LB_LIVE_USAGE_INGESTION_ENABLED", L"false"},
            {L"CODEX_LB_MODEL_REGISTRY_ENABLED", L"false"},
            {L"CODEX_LB_QUOTA_PLANNER_SCHEDULER_ENABLED", L"false"},
            {L"CODEX_LB_STICKY_SESSION_CLEANUP_ENABLED", L"false"},
            {L"CODEX_LB_USAGE_REFRESH_ENABLED", L"false"},
        };
        for (const auto& [name, value] : testEnvironment) {
            saved.push_back(SaveEnvironment(name));
            SetEnvironmentVariableW(name.c_str(), value.c_str());
        }
    }

    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION process{};
    const BOOL created = CreateProcessW(
        backendPath.c_str(),
        commandBuffer.data(),
        nullptr,
        nullptr,
        FALSE,
        CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT,
        nullptr,
        g_app.executableDir.c_str(),
        &startup,
        &process);
    const DWORD createError = created ? ERROR_SUCCESS : GetLastError();
    RestoreEnvironment(saved);
    if (!created) {
        error = L"Could not start the bundled backend: " + FormatWin32Error(createError);
        CloseHandle(g_app.shutdownEvent);
        g_app.shutdownEvent = nullptr;
        return false;
    }

    g_app.backendProcess = process.hProcess;
    g_app.backendThread = process.hThread;
    g_app.backendOwned = true;

    g_app.backendJob = CreateJobObjectW(nullptr, nullptr);
    if (g_app.backendJob) {
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        if (!SetInformationJobObject(
                g_app.backendJob,
                JobObjectExtendedLimitInformation,
                &limits,
                sizeof(limits)) ||
            !AssignProcessToJobObject(g_app.backendJob, g_app.backendProcess)) {
            AppendLifecycleLog(L"Backend job-object crash guard could not be enabled.");
            CloseHandle(g_app.backendJob);
            g_app.backendJob = nullptr;
        }
    }

    AppendLifecycleLog(L"Started owned backend on 127.0.0.1:" + std::to_wstring(g_app.options.port));
    return true;
}

bool WaitForBackendReady(std::chrono::seconds timeout, std::wstring& error) {
    const auto deadline = std::chrono::steady_clock::now() + timeout;
    while (std::chrono::steady_clock::now() < deadline && !g_app.closing.load()) {
        if (IsCodexLbHealthy(g_app.options.port)) {
            const HttpResponse ready = HttpGet(g_app.options.port, L"/health/ready");
            if (ready.transportOk && ready.status == 200 && ready.body.find("\"status\":\"ok\"") != std::string::npos) {
                return true;
            }
        }
        if (g_app.backendOwned && g_app.backendProcess && WaitForSingleObject(g_app.backendProcess, 0) == WAIT_OBJECT_0) {
            DWORD exitCode = 0;
            GetExitCodeProcess(g_app.backendProcess, &exitCode);
            error = L"The bundled backend stopped during startup (exit code " + std::to_wstring(exitCode) +
                    L"). Check " + (g_app.dataDir / L"logs").wstring() + L" for details.";
            return false;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(300));
    }
    error = L"Codex LB did not become ready within " + std::to_wstring(timeout.count()) +
            L" seconds. Check " + (g_app.dataDir / L"logs").wstring() + L" for details.";
    return false;
}

bool SignalBackendAndWait(DWORD timeoutMs) {
    if (!g_app.backendOwned || !g_app.backendProcess) return true;
    AppendLifecycleLog(L"Requesting graceful backend shutdown.");
    if (g_app.shutdownEvent) SetEvent(g_app.shutdownEvent);
    const DWORD waitResult = WaitForSingleObject(g_app.backendProcess, timeoutMs);
    if (waitResult == WAIT_OBJECT_0) {
        AppendLifecycleLog(L"Owned backend stopped gracefully.");
        return true;
    }
    AppendLifecycleLog(L"Owned backend exceeded the graceful shutdown deadline; stopping its exact process.");
    TerminateProcess(g_app.backendProcess, 2);
    WaitForSingleObject(g_app.backendProcess, 5000);
    return false;
}

void CloseBackendHandles() {
    if (g_app.backendThread) CloseHandle(g_app.backendThread);
    if (g_app.backendProcess) CloseHandle(g_app.backendProcess);
    if (g_app.shutdownEvent) CloseHandle(g_app.shutdownEvent);
    if (g_app.backendJob) CloseHandle(g_app.backendJob);
    g_app.backendThread = nullptr;
    g_app.backendProcess = nullptr;
    g_app.shutdownEvent = nullptr;
    g_app.backendJob = nullptr;
}

void BackendWorker() {
    SetStatus(L"Checking for a local Codex LB service...");
    if (IsCodexLbHealthy(g_app.options.port)) {
        g_app.backendReused = true;
        g_app.backendReady = true;
        AppendLifecycleLog(L"Reusing healthy backend on 127.0.0.1:" + std::to_wstring(g_app.options.port));
        PostMessageW(g_app.window, kMessageBackendReady, 0, 0);
        return;
    }
    if (IsPortListening(g_app.options.port)) {
        SetError(
            L"Port " + std::to_wstring(g_app.options.port) +
            L" is already in use by something that is not a healthy Codex LB service.\n\n"
            L"Close that application or run Codex LB with a different --port value.");
        return;
    }

    SetStatus(L"Starting the bundled Codex LB service...");
    std::wstring error;
    if (!StartOwnedBackend(error)) {
        SetError(error);
        return;
    }
    SetStatus(L"Codex LB is starting and preparing its local database...");
    if (!WaitForBackendReady(std::chrono::seconds(120), error)) {
        if (!g_app.closing.load()) SetError(error);
        return;
    }
    if (!g_app.closing.load()) {
        g_app.backendReady = true;
        PostMessageW(g_app.window, kMessageBackendReady, 0, 0);
    }
}

std::wstring LoadingHtml(const std::wstring& message, bool error = false) {
    std::wstring color = error ? L"#ff7b72" : L"#4f8ff7";
    std::wstring title = error ? L"Codex LB could not start" : L"Starting Codex LB";
    std::wstring safe = message;
    const std::vector<std::pair<std::wstring, std::wstring>> replacements = {
        {L"&", L"&amp;"}, {L"<", L"&lt;"}, {L">", L"&gt;"}, {L"\n", L"<br>"}};
    for (const auto& [source, target] : replacements) {
        size_t position = 0;
        while ((position = safe.find(source, position)) != std::wstring::npos) {
            safe.replace(position, source.size(), target);
            position += target.size();
        }
    }
    return LR"HTML(<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;background:#0d1117;color:#e8edf5;font:16px "Segoe UI",sans-serif;display:grid;place-items:center;height:100vh}
.card{width:min(660px,78vw);padding:42px;border:1px solid #29364f;border-radius:18px;background:linear-gradient(145deg,#182337,#101722);box-shadow:0 24px 70px #0008}
.mark{font-size:34px;font-weight:800;letter-spacing:-2px;margin-bottom:22px}.mark span{color:#4f8ff7}h1{font-size:26px;margin:0 0 14px}.status{color:#aebbd0;line-height:1.55}.pulse{width:9px;height:9px;border-radius:50%;background:)HTML" +
           color + LR"HTML(;display:inline-block;margin-right:10px;box-shadow:0 0 18px )HTML" + color +
           LR"HTML(}small{display:block;color:#697890;margin-top:24px}</style></head><body><div class="card"><div class="mark">L<span>B</span></div><h1>)HTML" +
           title + L"</h1><div class=\"status\"><span class=\"pulse\"></span>" + safe +
           L"</div><small>XA native Windows application</small></div></body></html>";
}

void ResizeWebView() {
    if (!g_app.webviewController || !g_app.window) return;
    RECT bounds{};
    GetClientRect(g_app.window, &bounds);
    g_app.webviewController->put_Bounds(bounds);
}

void NavigateToLoadingPage(const std::wstring& message, bool error = false) {
    if (g_app.webview) g_app.webview->NavigateToString(LoadingHtml(message, error).c_str());
}

void InitializeWebView() {
    const fs::path webviewData = g_app.dataDir / L"webview2";
    std::error_code directoryError;
    fs::create_directories(webviewData, directoryError);
    const HRESULT result = CreateCoreWebView2EnvironmentWithOptions(
        nullptr,
        webviewData.c_str(),
        nullptr,
        Callback<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler>(
            [](HRESULT environmentResult, ICoreWebView2Environment* environment) -> HRESULT {
                if (FAILED(environmentResult) || !environment) {
                    SetError(
                        L"Microsoft Edge WebView2 Runtime is required to display Codex LB.\n\n"
                        L"Install the Evergreen WebView2 Runtime, then open Codex LB again.\n\nWindows error: " +
                        FormatHResult(environmentResult));
                    return environmentResult;
                }
                return environment->CreateCoreWebView2Controller(
                    g_app.window,
                    Callback<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler>(
                        [](HRESULT controllerResult, ICoreWebView2Controller* controller) -> HRESULT {
                            if (FAILED(controllerResult) || !controller) {
                                SetError(L"The Codex LB web window could not be created: " + FormatHResult(controllerResult));
                                return controllerResult;
                            }
                            g_app.webviewController = controller;
                            controller->get_CoreWebView2(&g_app.webview);
                            ResizeWebView();
                            if (g_app.webview) {
                                ComPtr<ICoreWebView2Settings> settings;
                                if (SUCCEEDED(g_app.webview->get_Settings(&settings)) && settings) {
                                    settings->put_IsStatusBarEnabled(FALSE);
                                    settings->put_AreDevToolsEnabled(TRUE);
                                }
                                std::wstring status;
                                std::wstring error;
                                {
                                    std::lock_guard<std::mutex> guard(g_app.statusMutex);
                                    status = g_app.statusText;
                                    error = g_app.errorText;
                                }
                                if (g_app.backendReady.load()) {
                                    g_app.webview->Navigate(g_app.baseUrl.c_str());
                                } else {
                                    NavigateToLoadingPage(error.empty() ? status : error, !error.empty());
                                }
                            }
                            return S_OK;
                        })
                        .Get());
            })
            .Get());
    if (FAILED(result)) {
        SetError(L"The WebView2 loader could not initialize: " + FormatHResult(result));
    }
}

void PaintFallback(HWND window) {
    PAINTSTRUCT paint{};
    HDC dc = BeginPaint(window, &paint);
    RECT bounds{};
    GetClientRect(window, &bounds);
    HBRUSH background = CreateSolidBrush(RGB(13, 17, 23));
    FillRect(dc, &bounds, background);
    DeleteObject(background);
    SetBkMode(dc, TRANSPARENT);
    SetTextColor(dc, RGB(232, 237, 245));
    HFONT font = CreateFontW(
        24,
        0,
        0,
        0,
        FW_SEMIBOLD,
        FALSE,
        FALSE,
        FALSE,
        DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS,
        CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY,
        DEFAULT_PITCH | FF_DONTCARE,
        L"Segoe UI");
    HGDIOBJ oldFont = SelectObject(dc, font);
    std::wstring text;
    {
        std::lock_guard<std::mutex> guard(g_app.statusMutex);
        text = g_app.errorText.empty() ? g_app.statusText : g_app.errorText;
    }
    RECT textRect = bounds;
    InflateRect(&textRect, -70, -70);
    DrawTextW(dc, text.c_str(), -1, &textRect, DT_LEFT | DT_TOP | DT_WORDBREAK);
    SelectObject(dc, oldFont);
    DeleteObject(font);
    EndPaint(window, &paint);
}

LRESULT CALLBACK WindowProcedure(HWND window, UINT message, WPARAM wParam, LPARAM lParam) {
    switch (message) {
        case WM_SIZE:
            ResizeWebView();
            return 0;
        case WM_GETMINMAXINFO: {
            auto* info = reinterpret_cast<MINMAXINFO*>(lParam);
            info->ptMinTrackSize.x = 780;
            info->ptMinTrackSize.y = 560;
            return 0;
        }
        case kMessageBackendReady:
            AppendLifecycleLog(
                g_app.backendReused ? L"Dashboard ready using the existing backend." :
                                      L"Dashboard ready using the owned backend.");
            if (g_app.webview) g_app.webview->Navigate(g_app.baseUrl.c_str());
            return 0;
        case kMessageBackendError: {
            std::wstring error;
            {
                std::lock_guard<std::mutex> guard(g_app.statusMutex);
                error = g_app.errorText;
            }
            NavigateToLoadingPage(error, true);
            InvalidateRect(window, nullptr, TRUE);
            return 0;
        }
        case WM_PAINT:
            if (!g_app.webviewController) PaintFallback(window);
            else ValidateRect(window, nullptr);
            return 0;
        case WM_CLOSE:
            if (!g_app.closing.exchange(true)) {
                if (g_app.backendOwned) SignalBackendAndWait(30000);
                if (g_app.backendWorker.joinable()) g_app.backendWorker.join();
                CloseBackendHandles();
                AppendLifecycleLog(L"Native application closed.");
            }
            DestroyWindow(window);
            return 0;
        case WM_DESTROY:
            g_app.webview.Reset();
            g_app.webviewController.Reset();
            PostQuitMessage(0);
            return 0;
        default:
            return DefWindowProcW(window, message, wParam, lParam);
    }
}

bool ExtractFirstAsset(const std::string& html, const std::string& extension, std::wstring& assetPath) {
    size_t position = 0;
    while ((position = html.find("/assets/", position)) != std::string::npos) {
        const size_t end = html.find_first_of("\"'<> ", position);
        if (end == std::string::npos) return false;
        const std::string candidate = html.substr(position, end - position);
        if (candidate.size() >= extension.size() &&
            candidate.compare(candidate.size() - extension.size(), extension.size(), extension) == 0) {
            assetPath.assign(candidate.begin(), candidate.end());
            return true;
        }
        position = end;
    }
    return false;
}

std::string JsonEscape(const std::string& value) {
    std::string result;
    for (const char character : value) {
        switch (character) {
            case '\\': result += "\\\\"; break;
            case '"': result += "\\\""; break;
            case '\n': result += "\\n"; break;
            case '\r': result += "\\r"; break;
            case '\t': result += "\\t"; break;
            default: result += character; break;
        }
    }
    return result;
}

int RunSelfTest() {
    std::map<std::string, bool> checks = {
        {"assets_css", false},
        {"assets_js", false},
        {"dashboard_api", false},
        {"dashboard_html", false},
        {"encryption_key", false},
        {"graceful_shutdown", false},
        {"health", false},
        {"persistence", false},
        {"readiness", false},
    };
    std::string detail;
    if (IsPortListening(g_app.options.port)) {
        detail = "The self-test port was already in use.";
    } else {
        std::wstring error;
        if (!StartOwnedBackend(error)) {
            detail = WideToUtf8(error);
        } else if (!WaitForBackendReady(std::chrono::seconds(120), error)) {
            detail = WideToUtf8(error);
        } else {
            const HttpResponse health = HttpGet(g_app.options.port, L"/health");
            checks["health"] = health.status == 200 && !health.appVersion.empty();
            const HttpResponse ready = HttpGet(g_app.options.port, L"/health/ready");
            checks["readiness"] = ready.status == 200;
            const HttpResponse dashboard = HttpGet(g_app.options.port, L"/");
            checks["dashboard_html"] = dashboard.status == 200 && dashboard.body.find("<!doctype html") != std::string::npos;
            std::wstring jsPath;
            std::wstring cssPath;
            if (ExtractFirstAsset(dashboard.body, ".js", jsPath)) {
                const HttpResponse asset = HttpGet(g_app.options.port, jsPath);
                checks["assets_js"] = asset.status == 200 && !asset.body.empty();
            }
            if (ExtractFirstAsset(dashboard.body, ".css", cssPath)) {
                const HttpResponse asset = HttpGet(g_app.options.port, cssPath);
                checks["assets_css"] = asset.status == 200 && !asset.body.empty();
            }
            const HttpResponse overview = HttpGet(g_app.options.port, L"/api/dashboard/overview?timeframe=1d", 12000);
            checks["dashboard_api"] = overview.status == 200;
            checks["persistence"] = fs::is_regular_file(g_app.dataDir / L"store.db");
            checks["encryption_key"] = fs::is_regular_file(g_app.dataDir / L"encryption.key");
            checks["graceful_shutdown"] = SignalBackendAndWait(30000);
        }
    }
    if (g_app.backendOwned && g_app.backendProcess && WaitForSingleObject(g_app.backendProcess, 0) != WAIT_OBJECT_0) {
        SignalBackendAndWait(5000);
    }
    CloseBackendHandles();
    const bool passed = std::all_of(checks.begin(), checks.end(), [](const auto& item) { return item.second; });
    fs::create_directories(g_app.dataDir);
    const fs::path reportPath = g_app.dataDir / L"native-self-test.json";
    std::ofstream report(reportPath, std::ios::trunc);
    report << "{\n  \"passed\": " << (passed ? "true" : "false") << ",\n  \"version\": \"1.23.0-beta.2\",\n";
    report << "  \"port\": " << g_app.options.port << ",\n  \"checks\": {\n";
    size_t index = 0;
    for (const auto& [name, ok] : checks) {
        report << "    \"" << name << "\": " << (ok ? "true" : "false");
        report << (++index < checks.size() ? ",\n" : "\n");
    }
    report << "  },\n  \"detail\": \"" << JsonEscape(detail) << "\"\n}\n";
    return passed ? 0 : 1;
}

int RunWindowedApplication() {
    SetCurrentProcessExplicitAppUserModelID(L"XA.CodexLB");
    WNDCLASSEXW windowClass{};
    windowClass.cbSize = sizeof(windowClass);
    windowClass.style = CS_HREDRAW | CS_VREDRAW;
    windowClass.lpfnWndProc = WindowProcedure;
    windowClass.hInstance = g_app.instance;
    windowClass.hIcon = static_cast<HICON>(LoadImageW(
        g_app.instance, MAKEINTRESOURCEW(IDI_CODEX_LB), IMAGE_ICON, 0, 0, LR_DEFAULTSIZE));
    windowClass.hIconSm = static_cast<HICON>(LoadImageW(
        g_app.instance, MAKEINTRESOURCEW(IDI_CODEX_LB), IMAGE_ICON, 16, 16, LR_DEFAULTCOLOR));
    windowClass.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    windowClass.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1);
    windowClass.lpszClassName = kWindowClass;
    if (!RegisterClassExW(&windowClass)) {
        MessageBoxW(nullptr, FormatWin32Error(GetLastError()).c_str(), L"Codex LB", MB_OK | MB_ICONERROR);
        return 1;
    }

    RECT desired{0, 0, 1280, 840};
    AdjustWindowRectEx(&desired, WS_OVERLAPPEDWINDOW, FALSE, 0);
    const int width = desired.right - desired.left;
    const int height = desired.bottom - desired.top;
    const int x = std::max(0, (GetSystemMetrics(SM_CXSCREEN) - width) / 2);
    const int y = std::max(0, (GetSystemMetrics(SM_CYSCREEN) - height) / 2);
    g_app.window = CreateWindowExW(
        0,
        kWindowClass,
        kWindowTitle,
        WS_OVERLAPPEDWINDOW,
        x,
        y,
        width,
        height,
        nullptr,
        nullptr,
        g_app.instance,
        nullptr);
    if (!g_app.window) {
        MessageBoxW(nullptr, FormatWin32Error(GetLastError()).c_str(), L"Codex LB", MB_OK | MB_ICONERROR);
        return 1;
    }
    ShowWindow(g_app.window, SW_SHOW);
    UpdateWindow(g_app.window);
    InitializeWebView();
    g_app.backendWorker = std::thread(BackendWorker);

    MSG message{};
    while (GetMessageW(&message, nullptr, 0, 0) > 0) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
    if (g_app.backendWorker.joinable()) g_app.backendWorker.join();
    return static_cast<int>(message.wParam);
}

}  // namespace

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int) {
    g_app.instance = instance;
    g_app.executableDir = ModuleDirectory();
    std::wstring optionError;
    if (!ParseOptions(g_app.options, optionError)) {
        MessageBoxW(nullptr, optionError.c_str(), L"Codex LB", MB_OK | MB_ICONERROR);
        return 2;
    }
    g_app.dataDir = g_app.options.dataDir.empty() ? DefaultDataDirectory() : fs::absolute(g_app.options.dataDir);
    g_app.options.dataDir = g_app.dataDir;
    g_app.baseUrl = L"http://127.0.0.1:" + std::to_wstring(g_app.options.port) + L"/";
    try {
        fs::create_directories(g_app.dataDir);
    } catch (const std::exception&) {
        MessageBoxW(nullptr, L"The Codex LB data directory could not be created.", L"Codex LB", MB_OK | MB_ICONERROR);
        return 2;
    }
    AppendLifecycleLog(L"Native application starting, version " CODEX_LB_NATIVE_VERSION L".");

    WSADATA winsock{};
    if (WSAStartup(MAKEWORD(2, 2), &winsock) != 0) {
        MessageBoxW(nullptr, L"Windows networking could not initialize.", L"Codex LB", MB_OK | MB_ICONERROR);
        return 2;
    }
    const HRESULT comResult = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    if (FAILED(comResult)) {
        WSACleanup();
        MessageBoxW(nullptr, FormatHResult(comResult).c_str(), L"Codex LB", MB_OK | MB_ICONERROR);
        return 2;
    }

    const int result = g_app.options.selfTest ? RunSelfTest() : RunWindowedApplication();
    if (g_app.backendOwned && g_app.backendProcess) {
        SignalBackendAndWait(5000);
        CloseBackendHandles();
    }
    CoUninitialize();
    WSACleanup();
    return result;
}
