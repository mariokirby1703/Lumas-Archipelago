// Experimental, unbuilt. One-shot command, executed only by WH_GETMESSAGE.
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <cstdio>

struct Command {
    std::uint32_t magic, version;
    volatile LONG state;  // 0 idle, 1 pending, 2 executing, 3 returned, 4 rejected
    std::uint32_t opcode, target_pid, target_thread, error, context_before;
};
static_assert(sizeof(Command) == 32);
constexpr std::uint32_t Magic = 0x4c435544;

// Runs within the game's window thread. Never changes the context index directly.
static DWORD Execute(Command* command) {
    __try {
        const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
        const unsigned char prefix[] = {0x48,0x89,0x5c,0x24,0x08,0x48,0x89,0x6c,0x24,0x10};
        if (std::memcmp(reinterpret_cast<void*>(base + 0x79ad00), prefix, sizeof(prefix))) return 1;
        const auto actor = *reinterpret_cast<std::uintptr_t*>(base + 0x1c7d3e0);
        if (!actor || !(*reinterpret_cast<std::uint32_t*>(actor + 0xd4) & 0x1000)) return 2;
        if (*reinterpret_cast<unsigned char*>(actor + 0x3e3) == 0xff) return 3;
        const auto current = *reinterpret_cast<int*>(actor + 0x6b0);
        const auto secondary = *reinterpret_cast<int*>(actor + 0x6b8);
        const auto action = *reinterpret_cast<std::uintptr_t*>(actor + 0x6c0);
        const int context = current == secondary && action
            ? *reinterpret_cast<short*>(action + 0x11e) : current;
        command->context_before = static_cast<std::uint32_t>(context);
        // This first experiment accepts only the observed ordinary Default state.
        if (context != 46 || !*reinterpret_cast<unsigned char*>(actor + 0x943)) return 4;
        using Kill = int (*)(void*, int, void*, int, void*, int, int);
        const auto kill = reinterpret_cast<Kill>(base + 0x79ad00);
        kill(reinterpret_cast<void*>(actor), 3, nullptr, 1, nullptr, 0, 0);
        return 0;
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        // This reports a fault; it cannot roll back partial native side effects.
        return 5;
    }
}

extern "C" __declspec(dllexport) LRESULT CALLBACK BridgeHook(int code, WPARAM wparam, LPARAM lparam) {
    if (code >= 0 && wparam == PM_REMOVE) {
        wchar_t name[80]{};
        swprintf_s(name, L"Local\\LCUDeathBridge_%lu", GetCurrentProcessId());
        const auto mapping = OpenFileMappingW(FILE_MAP_ALL_ACCESS, FALSE, name);
        if (mapping) {
            auto command = static_cast<Command*>(MapViewOfFile(mapping, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(Command)));
            if (command) {
                if (command->magic == Magic && command->version == 1 && command->opcode == 1 &&
                    command->target_pid == GetCurrentProcessId() && command->target_thread == GetCurrentThreadId() &&
                    InterlockedCompareExchange(&command->state, 2, 1) == 1) {
                    command->error = Execute(command);
                    InterlockedExchange(&command->state, command->error ? 4 : 3);
                }
                UnmapViewOfFile(command);
            }
            CloseHandle(mapping);
        }
    }
    return CallNextHookEx(nullptr, code, wparam, lparam);
}
