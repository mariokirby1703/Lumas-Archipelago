#include <windows.h>
#include <cstdint>
#include <cstring>
#include <cmath>
#include "native_context_policy.h"
struct Command {
    std::uint32_t magic,version;volatile LONG state;
    std::uint32_t opcode,pid,thread,error,model,name_hash,found,owned,receipt,binding[4];
};
static_assert(sizeof(Command)==64);
#include "../../bridge/native/command_dispatch.h"
extern "C" __declspec(dllexport) DWORD ClaimPacket(Command* c,DWORD pid,DWORD thread) {
    return ClaimCommand(c,pid,thread) ? 1 : 0;
}
static std::uint32_t Hash(const char* text) {
    std::uint32_t h=0x811c9dc5;
    for(unsigned i=0;i<256;++i) {unsigned char c=text[i];if(!c)return h;
        if(c>='a' && c<='z')c-=32;h=(h*0x1000193)^c;}
    return 0;
}
#include "../../bridge/native/station_exit.h"
extern "C" __declspec(dllexport) DWORD TestStationExit(std::uintptr_t base,std::uintptr_t actor,std::uint32_t* triggered) {
    Command c{};c.name_hash=Hash("STATION_EXIT");
    DWORD result=TriggerStationExit(base,actor,&c);*triggered=c.found;return result;
}
#include "../../bridge/native/lobby_lift.h"
extern "C" __declspec(dllexport) DWORD TestLobbyLift(std::uintptr_t base,std::uintptr_t actor,std::uint32_t* opened) {
    Command c{};c.name_hash=Hash("OPEN_LOBBY_LIFT");
    DWORD result=OpenLobbyLift(base,actor,&c);*opened=c.found;return result;
}
#include "../../bridge/native/tutorial_fields.h"
#include "../../bridge/native/chief_key.h"
#include "../../bridge/native/test_items.h"
extern "C" __declspec(dllexport) DWORD TestLocalCurrency(std::uintptr_t base,unsigned amount,unsigned hash) {
    Command c{};c.model=amount;c.name_hash=hash;return TestCurrency(base,&c);
}
extern "C" __declspec(dllexport) DWORD TestLocalRemove(std::uintptr_t base,std::uintptr_t actor,unsigned kind,unsigned index,unsigned hash) {
    Command c{};c.receipt=kind;c.model=index;c.name_hash=hash;return TestRemove(base,actor,&c);
}
extern "C" __declspec(dllexport) DWORD TestChiefRadio(std::uintptr_t base,std::uintptr_t actor,std::uint32_t* changed) {
    Command c{};c.name_hash=Hash("CHIEF_RADIO");
    DWORD result=RevealChiefRadio(base,actor,&c);*changed=c.found;return result;
}
extern "C" __declspec(dllexport) DWORD TestChiefKey(std::uintptr_t base,std::uintptr_t actor,std::uint32_t* changed) {
    Command c{};c.name_hash=Hash("CHIEF_KEY");
    DWORD result=UnlockChiefKey(base,actor,&c);*changed=c.found;return result;
}
extern "C" __declspec(dllexport) DWORD TestTutorialFields(std::uintptr_t base,std::uintptr_t actor,std::uint32_t* changed) {
    Command c{};c.name_hash=Hash("TUTORIAL_FIELDS");
    DWORD result=RelaxTutorialFields(base,actor,&c);*changed=c.found;return result;
}
