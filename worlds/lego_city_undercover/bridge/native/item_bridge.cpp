// Experimental model-grant endpoint. Host must verify the pinned EXE hash and
// execution-thread identity before installing this hook. Client.py requires opt-in.
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <cwchar>
#include <cmath>
#include "booth_selection_patch.h"
#include "native_context_policy.h"

struct Command {
    std::uint32_t magic, version;
    volatile LONG state;
    std::uint32_t opcode, pid, thread, error, model, name_hash, found, owned;
    std::uint32_t receipt, binding[4];
};
static_assert(sizeof(Command)==64);
#include "command_dispatch.h"
static std::uint32_t Hash(const char* value) {
    std::uint32_t h=0x811c9dc5;
    for(unsigned n=0;n<256;++n) {
        unsigned char c=value[n];
        if(!c)return h;
        if(c>='a' && c<='z')c-=32;
        h=(h*0x1000193)^c;
    }
    return 0;
}
#include "purchase_gate.h"
#include "reward_enforcement.h"
#include "currency_batch.h"
#include "station_exit.h"
#include "lobby_lift.h"
#include "tutorial_fields.h"
#include "chief_key.h"
#include "test_items.h"
static bool WriteCode(unsigned char* code,const unsigned char* replacement,std::size_t size) {
    if(!std::memcmp(code,replacement,size))return true;
    DWORD previous=0;
    if(!VirtualProtect(code,size,PAGE_EXECUTE_READWRITE,&previous))return false;
    std::memcpy(code,replacement,size);
    const bool flushed=FlushInstructionCache(GetCurrentProcess(),code,size)!=0;
    DWORD ignored=0;
    const bool restored=VirtualProtect(code,size,previous,&ignored)!=0;
    return flushed && restored;
}
static bool EnableOwnedBoothSelection(std::uintptr_t base) {
    // Navigation 0x267dd0 rejects unfound entries BEFORE the downstream input
    // gate is reached. Both paths must combine ownership with discovery.
    auto first=reinterpret_cast<unsigned char*>(base+navigation_rva_0);
    auto second=reinterpret_cast<unsigned char*>(base+navigation_rva_1);
    const unsigned char legacy_original[]={0x45,0x85,0xf6};
    const unsigned char legacy_patched[]={0x41,0x09,0xde};
    auto legacy=reinterpret_cast<unsigned char*>(base+0x26e067);
    if((std::memcmp(first,navigation_original_0,sizeof(navigation_original_0)) &&
        std::memcmp(first,navigation_replacement_0,sizeof(navigation_replacement_0))) ||
       (std::memcmp(second,navigation_original_1,sizeof(navigation_original_1)) &&
        std::memcmp(second,navigation_replacement_1,sizeof(navigation_replacement_1))) ||
       (std::memcmp(legacy,legacy_original,sizeof(legacy_original)) &&
        std::memcmp(legacy,legacy_patched,sizeof(legacy_patched))))return false;
    if(!WriteCode(first,navigation_replacement_0,sizeof(navigation_replacement_0)))return false;
    if(!WriteCode(second,navigation_replacement_1,sizeof(navigation_replacement_1))) {
        WriteCode(first,navigation_original_0,sizeof(navigation_original_0));return false;
    }
    // Revert the ineffective earlier experiment, preserving the native mode gate.
    return WriteCode(legacy,legacy_original,sizeof(legacy_original));
}
static DWORD Execute(Command* c) {
    __try {
        const auto base=reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
        const unsigned char owned_prefix[]={0x48,0x63,0xc2,0xc6,0x84,0x08,0x80,0,0,0,1};
        const unsigned char found_prefix[]={0x4c,0x63,0xca,0x4c,0x8b,0xd1};
        if(std::memcmp(reinterpret_cast<void*>(base+0x88a290),owned_prefix,sizeof(owned_prefix)) ||
           std::memcmp(reinterpret_cast<void*>(base+0x88a2b0),found_prefix,sizeof(found_prefix)))return 1;
        auto actor=*reinterpret_cast<std::uintptr_t*>(base+0x1c7d3e0);
        if(!actor || !(*reinterpret_cast<std::uint32_t*>(actor+0xd4)&0x1000))return 2;
        // Vehicle contexts permit passive receipts; reward revocation remains Default-only.
        const auto current=*reinterpret_cast<int*>(actor+0x6b0);
        const auto secondary=*reinterpret_cast<int*>(actor+0x6b8);
        const auto action=*reinterpret_cast<std::uintptr_t*>(actor+0x6c0);
        if(!action)return 3;
        const int context=current==secondary ? *reinterpret_cast<short*>(action+0x11e) : current;
        if(!AllowsNativeCommand(context,c->opcode,*reinterpret_cast<unsigned char*>(actor+0x943)!=0))return 3;
        if(c->opcode==14)return RelaxTutorialFields(base,actor,c);
        if(c->opcode==15)return UnlockChiefKey(base,actor,c);
        if(c->opcode==16)return RevealChiefRadio(base,actor,c);
        if(c->opcode==17)return TestCurrency(base,c);
        if(c->opcode==18)return TestRemove(base,actor,c);
        if(c->opcode==13)return OpenLobbyLift(base,actor,c);
        if(c->opcode==12)return TriggerStationExit(base,actor,c);
        if(c->opcode==8 || c->opcode==9)return EnforceRewards(base,actor,c,c->opcode==9);
        if(c->opcode==10)return CreditBatch(base,c);
        if(c->opcode==6 || c->opcode==7) {
            const bool studs=c->opcode==6;
            if(Hash(studs ? "ADD_STUDS" : "ADD_BRICKS")!=c->name_hash)return 6;
            const auto amount=c->model;
            if(studs ? (amount!=1000 && amount!=10000 && amount!=100000) :
                       (amount!=100 && amount!=250 && amount!=1000 && amount!=10000))return 9;
            auto stats=*reinterpret_cast<std::uintptr_t*>(base+0x1c7a830);
            auto profile=*reinterpret_cast<std::uintptr_t*>(base+0x1c7f160);
            auto bank=*reinterpret_cast<std::uintptr_t*>(base+0x1c7cbb8);
            auto models=*reinterpret_cast<std::uintptr_t*>(base+0x17ebd38);
            if(!stats || !profile || !bank || !models)return 4;
            if(bank!=profile+0x122e0)return 5;
            if(*reinterpret_cast<std::uint32_t*>(models+0xe0)!=1002 || c->receipt==UINT32_MAX)return 9;
            if(!(c->binding[0]|c->binding[1]|c->binding[2]|c->binding[3]))return 6;
            auto marker=reinterpret_cast<unsigned char*>(bank+0x80+1002);
            bool empty=true;
            for(unsigned i=0;i<22;++i)empty=empty && marker[i]==0;
            std::uint32_t next=0;
            if(!empty) {
                if(marker[0]!='A' || marker[1]!='P' || std::memcmp(marker+2,c->binding,16))return 13;
                std::memcpy(&next,marker+18,4);
                if(c->receipt<next) { c->owned=1;c->found=0;return 0; }
            }
            auto controller=stats+0x3638;
            if(!*reinterpret_cast<unsigned char*>(controller+0x21))return 11;
            if(*reinterpret_cast<unsigned char*>(controller+0x23) ||
               *reinterpret_cast<unsigned char*>(controller+0x20)!=0)return 14;
            const unsigned char save_prefix[]={0x80,0x79,0x21,0};
            if(std::memcmp(reinterpret_cast<void*>(base+0xd18b0),save_prefix,sizeof(save_prefix)))return 1;
            if(studs) {
                // Same persistent profile field credited by 0xa003d4/0x8ea520.
                // AP packages are exact amounts, independent of pickup multipliers.
                auto balance=reinterpret_cast<std::uint64_t*>(profile+0xfb10);
                const auto prior=*balance;
                if(prior>UINT64_MAX-amount)return 12;
                *balance=prior+amount;
                c->owned=*balance==prior+amount;
            } else {
                const unsigned char get_prefix[]={0x80,0xb9,0x5d,0x33,0,0,0};
                if(std::memcmp(reinterpret_cast<void*>(base+0x3bf70),get_prefix,sizeof(get_prefix)) ||
                   std::memcmp(reinterpret_cast<void*>(base+0x40e30),get_prefix,sizeof(get_prefix)))return 1;
                using Get=std::uint32_t(*)(void*);
                using Set=void(*)(void*,std::uint32_t);
                auto get=reinterpret_cast<Get>(base+0x3bf70);
                auto set=reinterpret_cast<Set>(base+0x40e30);
                const auto prior=get(reinterpret_cast<void*>(stats));
                if(prior>INT32_MAX-amount)return 12;
                set(reinterpret_cast<void*>(stats),prior+amount);
                c->owned=get(reinterpret_cast<void*>(stats))==prior+amount;
            }
            if(!c->owned)return 7;
            marker[0]='A';marker[1]='P';std::memcpy(marker+2,c->binding,16);
            next=c->receipt+1;std::memcpy(marker+18,&next,4);
            using Save=void(*)(void*);
            reinterpret_cast<Save>(base+0xd18b0)(reinterpret_cast<void*>(controller));
            c->found=*reinterpret_cast<unsigned char*>(controller+0x23);
            return c->owned ? 0 : 7;
        }
        if(c->opcode==5) {
            if(c->model || Hash("AUTOSAVE")!=c->name_hash)return 6;
            const unsigned char prefix[]={0x80,0x79,0x21,0x00};
            if(std::memcmp(reinterpret_cast<void*>(base+0xd18b0),prefix,sizeof(prefix)))return 1;
            auto stats=*reinterpret_cast<std::uintptr_t*>(base+0x1c7a830);
            if(!stats)return 4;
            auto controller=stats+0x3638;
            if(!*reinterpret_cast<unsigned char*>(controller+0x21))return 11;
            using Save=void(*)(void*);
            reinterpret_cast<Save>(base+0xd18b0)(reinterpret_cast<void*>(controller));
            c->found=*reinterpret_cast<unsigned char*>(controller+0x23);
            c->owned=*reinterpret_cast<unsigned char*>(controller+0x20);
            return c->found && c->owned==2 ? 0 : 7;
        }
        if(c->opcode==3) {
            auto manager=*reinterpret_cast<std::uintptr_t*>(base+0x11755f8);
            if(!manager)return 4;
            const auto count=*reinterpret_cast<std::uint32_t*>(manager+8);
            if(!count || count>64 || c->model>=count)return 5;
            auto table=*reinterpret_cast<std::uintptr_t*>(manager);
            auto definition=*reinterpret_cast<std::uintptr_t*>(table+c->model*32);
            auto name=*reinterpret_cast<const char**>(definition);
            if(!name || Hash(name)!=c->name_hash)return 6;
            auto found=*reinterpret_cast<std::uint64_t**>(base+0x1c7e848);
            auto effect=*reinterpret_cast<std::uint64_t**>(base+0x1c7e850);
            if(!found || !effect)return 4;
            const auto mask=std::uint64_t(1)<<c->model;
            const unsigned char prefix[]={0x57,0x48,0x83,0xec,0x50};
            if(std::memcmp(reinterpret_cast<void*>(base+0x7f19a0),prefix,sizeof(prefix)))return 1;
            if(!(*effect&mask)) {
                // edx=0 skips the original pickup's mission/reward bookkeeping.
                using Unlock=void(*)(int,int,bool);
                reinterpret_cast<Unlock>(base+0x7f19a0)(c->model,0,false);
            }
            c->found=!!(*found&mask);c->owned=!!(*effect&mask);
            return c->owned ? 0 : 7;
        }
        if(c->opcode==2) {
            static const char* names[]={"GrappleGun","EnergyGun","SuperBuild","Parkour","Grab","TargetThrow","FinishingMove","Parry",
                "Scanner","Map","Camera","Surveillance","Wiretap","DataScanner","Snapshot","Album","Ellie",
                "Policestation","Jetpack","FireAxe","Pigs","FastTravel","SF_Residential","SF_Docks","WI_Farmlands",
                "WI_Forest","BR_Brooklyn_Bridge","BR_Golden_Gate","BR_Twin_Bridge","IS_Liberty_Island","IS_Prison_Island",
                "IS_Space_Centre","NY_Airport","NY_Beach","NY_Canal","NY_Central_Park","NY_Chinatown","NY_Downtown",
                "NY_Downtown_East","NY_Downtown_West","NY_Little_Italy","NY_Times_Square","NY_Tunnel","NY_Uptown",
                "Unassigned District","Bonus_Missions","DisguiseBooth","Race","SuperStrength","Act2","2x_Brick_Multi"};
            if(c->model>=51 || Hash(names[c->model])!=c->name_hash)return 9;
            const unsigned char prefix[]={0x48,0x83,0xec,0x48};
            if(std::memcmp(reinterpret_cast<void*>(base+0x90e00),prefix,sizeof(prefix)))return 1;
            auto manager=*reinterpret_cast<std::uintptr_t*>(base+0x17ebd48);
            if(!manager)return 4;
            auto id=static_cast<unsigned char>(c->model);
            using Unlock=void(*)(void*,unsigned char*,bool,bool);
            reinterpret_cast<Unlock>(base+0x90e00)(reinterpret_cast<void*>(manager),&id,true,true);
            c->found=*reinterpret_cast<unsigned char*>(manager+0xd8+c->model);
            c->owned=c->found;
            return c->found==1 ? 0 : 7;
        }
        auto models=*reinterpret_cast<std::uintptr_t*>(base+0x17ebd38);
        auto bank=*reinterpret_cast<std::uintptr_t*>(base+0x1c7cbb8);
        if(!models || !bank)return 4;
        const auto count=*reinterpret_cast<std::uint32_t*>(models+0xe0);
        if(!count || count>1024 || c->model>=count)return 5;
        auto table=*reinterpret_cast<std::uintptr_t*>(models+0x118);
        auto record=*reinterpret_cast<std::uintptr_t*>(table+c->model*8);
        auto name=*reinterpret_cast<const char**>(record+0x30);
        if(!name || Hash(name)!=c->name_hash)return 6;
        using Grant=void(*)(void*,int);
        auto found=reinterpret_cast<unsigned char*>(bank)+(c->model/8);
        auto owned=reinterpret_cast<unsigned char*>(bank)+0x80+c->model;
        if(c->opcode==4) {
            const unsigned char prefix[]={0x48,0x89,0x5c,0x24,0x10,0x56};
            if(std::memcmp(reinterpret_cast<void*>(base+0x88c020),prefix,sizeof(prefix)))return 1;
            using Available=int(*)(int,int);
            c->found=!!(*found & (1u<<(c->model%8)));
            c->owned=reinterpret_cast<Available>(base+0x88c020)(c->model,-1);
            return 0;
        }
        if(!EnableOwnedBoothSelection(base))return 10;
        // AP ownership must not mark a world character token as discovered.
        if(!*owned)
            reinterpret_cast<Grant>(base+0x88a290)(reinterpret_cast<void*>(bank),c->model);
        c->found=!!(*found & (1u<<(c->model%8)));c->owned=*owned;
        return c->owned ? 0 : 7;
    } __except(EXCEPTION_EXECUTE_HANDLER) { return 8; }
}
extern "C" __declspec(dllexport) LRESULT CALLBACK ItemBridgeHook(int code,WPARAM wparam,LPARAM lparam) {
    if(code>=0 && wparam==PM_REMOVE) {
        wchar_t name[80]{};
        swprintf(name,80,L"Local\\LCUItemBridge2_%lu",GetCurrentProcessId());
        HANDLE mapping=OpenFileMappingW(FILE_MAP_ALL_ACCESS,FALSE,name);
        if(mapping) {
            auto c=static_cast<Command*>(MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Command)));
            if(c) {
                if(ClaimCommand(c,GetCurrentProcessId(),GetCurrentThreadId())) {
                    c->error=Execute(c);InterlockedExchange(&c->state,c->error?4:3);
                }
                UnmapViewOfFile(c);
            }
            CloseHandle(mapping);
        }
    }
    return CallNextHookEx(nullptr,code,wparam,lparam);
}
