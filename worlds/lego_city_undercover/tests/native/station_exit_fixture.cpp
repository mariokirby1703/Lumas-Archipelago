#include <windows.h>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <cwchar>
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
#include "../../bridge/native/detective_gate.h"
#include "../../bridge/native/area_return.h"
extern "C" __declspec(dllexport) DWORD TestAreaReturn(std::uintptr_t base,std::uintptr_t actor,unsigned opcode,int context,unsigned district) {
    if(!opcode) {area_checkpoint={};area_foot_checkpoint={};area_disembark_pending=false;
        for(auto& entry:area_history)entry={};area_history_cursor=0;return 0;}
    Command c{};c.opcode=opcode;c.model=district;c.binding[0]=c.binding[1]=c.binding[2]=c.binding[3]=1;
    c.name_hash=Hash(opcode==21 ? "AREA_CHECKPOINT" : opcode==23 ? "AREA_DISEMBARK" : "AREA_RETURN");
    return AreaReturnCommand(base,actor,context,&c);
}
extern "C" __declspec(dllexport) DWORD TestDetectiveGate(std::uintptr_t base,unsigned mode) {
    const unsigned char prefix[]={0x40,0x57,0x48,0x83,0xec,0x50,0x48,0xc7,0x44,0x24,0x20,0xfe,0xff,0xff,0xff};
    auto entry=reinterpret_cast<unsigned char*>(base+0x649a0);
    auto observed=reinterpret_cast<unsigned char*>(base+0x2058000);
    *observed=99;std::memcpy(entry,prefix,15);
    // Fake native body records DL, then restores the exact original stack frame.
    unsigned char body[]={0x48,0xb8,0,0,0,0,0,0,0,0,0x88,0x10,0x48,0x83,0xc4,0x50,0x5f,0xc3};
    auto address=reinterpret_cast<std::uintptr_t>(observed);std::memcpy(body+2,&address,8);
    std::memcpy(entry+15,body,sizeof(body));FlushInstructionCache(GetCurrentProcess(),entry,33);
    detective_original=nullptr;detective_policy=0;
    if(mode==4)entry[0]=0x90;
    auto error=ConfigureDetectiveGate(base,123,1);
    if(error)return 100+error;
    if(mode==1 || mode==2)error=ConfigureDetectiveGate(base,123,3);
    if(mode==3)error=ConfigureDetectiveGate(base,123,0);
    if(!error)reinterpret_cast<DetectiveSetter>(entry)(123,mode!=2);
    auto result=*observed;
    auto trampoline=reinterpret_cast<void*>(detective_original);
    detective_original=nullptr;detective_policy=0;
    VirtualFree(trampoline,0,MEM_RELEASE);
    return error ? 100+error : result;
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
#include "../../bridge/native/item_popups.h"
extern "C" __declspec(dllexport) DWORD TestPopupScreen(std::uintptr_t base,unsigned mode) {
    auto screen=base+0x2059000,slot=screen+0x1000;
    *reinterpret_cast<std::uintptr_t*>(base+0x1803d98)=mode==1 ? 0 : screen;
    *reinterpret_cast<std::uintptr_t*>(base+0x1803da0)=mode==2 ? 0 : screen+0x2000;
    *reinterpret_cast<unsigned char*>(screen+8)=mode>=3;
    *reinterpret_cast<std::uintptr_t*>(slot+0xa8)=mode==4 ? screen : 0;
    return PopupScreenAvailable(base,slot) ? 1 : 0;
}
extern "C" __declspec(dllexport) DWORD TestPopupTint(std::uintptr_t base,unsigned mode,unsigned classification) {
    auto hud=base+0x2050000,slots=hud+0x1000,slot=hud+0x2000,obj=hud+0x3000;
    *reinterpret_cast<std::uintptr_t*>(base+0x183d088)=hud;
    *reinterpret_cast<std::uintptr_t*>(hud+0x40)=slots;
    *reinterpret_cast<std::uintptr_t*>(slots+24)=slot;
    *reinterpret_cast<std::uintptr_t*>(slot+8)=obj;
    auto rgb=PopupRGB(classification);
    auto colour=reinterpret_cast<std::uint32_t*>(obj+0xc8);
    *colour=0x55000000|rgb;
    popup_tint={};popup_tint.base=base;popup_tint.hud=hud;popup_tint.slot=slot;
    popup_tint.text_object=obj;popup_tint.original_rgb=0x00ffad4a;popup_tint.ap_rgb=rgb;
    popup_tint.timer=UINT_PTR(-1);popup_tint.deadline=0;
    if(mode==1)*colour=0xaa123456; // A newer native style must win.
    if(mode==2)*reinterpret_cast<std::uintptr_t*>(slot+8)=obj+0x1000; // Scene replaced object.
    if(mode==3)PopupTintTimer(nullptr,0,popup_tint.timer,0); // Expired timer restores style.
    else EndPopupTint();
    return *colour;
}
extern "C" __declspec(dllexport) DWORD TestPopupPosition(std::uintptr_t base,unsigned mode,float* output) {
    auto hud=base+0x2050000,slots=hud+0x1000,slot=hud+0x2000,obj=hud+0x3000;
    *reinterpret_cast<std::uintptr_t*>(base+0x183d088)=hud;
    *reinterpret_cast<std::uintptr_t*>(hud+0x40)=slots;
    *reinterpret_cast<std::uintptr_t*>(slots+24)=slot;
    *reinterpret_cast<std::uintptr_t*>(slot+8)=obj;
    popup_tint={};popup_tint.base=base;popup_tint.hud=hud;popup_tint.slot=slot;
    popup_tint.text_object=obj;popup_tint.timer=UINT_PTR(-1);popup_tint.moved=true;
    popup_tint.original_y=240;popup_tint.original_default_y=241;
    popup_tint.ap_y=480;popup_tint.ap_default_y=481;
    *reinterpret_cast<float*>(obj+0x74)=mode==1 ? 12 : 480;
    *reinterpret_cast<float*>(obj+0xb4)=481;
    if(mode==2)*reinterpret_cast<std::uintptr_t*>(slot+8)=obj+0x1000;
    EndPopupTint();
    output[0]=*reinterpret_cast<float*>(obj+0x74);output[1]=*reinterpret_cast<float*>(obj+0xb4);
    return *reinterpret_cast<unsigned char*>(obj+9)&2;
}
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
