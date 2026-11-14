#include "tutorial_flow.h"
// Only the two early station interaction pads; no global Police/class bypass.
static DWORD RelaxTutorialFields(std::uintptr_t base,std::uintptr_t actor,Command* c) {
    if(c->model || c->name_hash!=Hash("TUTORIAL_FIELDS"))return 6;
    c->found=0;c->owned=0;
    auto bank=*reinterpret_cast<std::uintptr_t*>(base+0x1c7cbb8);
    if(!bank)return 4;
    // AP ownership never sets this genuine COP source-discovery bit.
    if(!(*reinterpret_cast<unsigned char*>(bank+227/8)&(1u<<(227%8))))return 0;
    auto registry=*reinterpret_cast<std::uintptr_t*>(base+0x1c402d8);
    const auto scene_index=*reinterpret_cast<unsigned short*>(actor+0x28);
    if(!registry || scene_index>0x7ff)return 5;
    auto entry=*reinterpret_cast<std::uintptr_t*>(registry+0x18+scene_index*8);
    if(!entry)return 4;
    auto owner=*reinterpret_cast<std::uintptr_t*>(entry+0xd8);
    if(!owner)return 4;
    auto tile=*reinterpret_cast<std::uintptr_t*>(owner+0xb18);
    if(!tile)return 4;
    auto scene_name=*reinterpret_cast<const char**>(tile+0x68);
    if(!scene_name)return 4;
    const bool garage=Hash(scene_name)==Hash("POLICE_STATION_GARAGE");
    if(!garage && Hash(scene_name)!=Hash("POLICE_STATION_LOBBY"))return 0;
    if(!garage) {
        // The actual garage script writes PDA.acquired at ActivateLiftDoors,
        // after the basement sequence, not upon merely entering the garage.
        auto acquired=LobbyField(base,"PDA","acquired",0xc46bb8);
        if(!acquired || *reinterpret_cast<unsigned char*>(acquired+16)!=1)return 0;
    }
    auto level=*reinterpret_cast<std::uintptr_t*>(owner+0xbb0);
    if(!level)return 4;
    auto data=*reinterpret_cast<std::uintptr_t*>(level+0xa0);
    if(!data)return 4;
    auto table=*reinterpret_cast<std::uintptr_t*>(data+0xc0);
    auto system=*reinterpret_cast<std::uintptr_t*>(base+0x17ec098);
    if(!table || !system || *reinterpret_cast<std::uintptr_t*>(system)!=base+0xc34ae8)return 5;
    const auto index=*reinterpret_cast<int*>(system+0xf4);
    if(index<0 || index>=256)return 5;
    auto component=*reinterpret_cast<std::uintptr_t*>(table+index*8);
    if(!component || *reinterpret_cast<std::uintptr_t*>(component)!=base+0xc34ed8)return 5;
    auto node=*reinterpret_cast<std::uintptr_t*>(component+0xe0);
    std::uintptr_t target=0,visited[1024]{};unsigned count=0;
    while(node) {
        if(count>=1024)return 5;
        for(unsigned i=0;i<count;++i)if(visited[i]==node)return 5;
        visited[count++]=node;
        if(*reinterpret_cast<std::uintptr_t*>(node)!=base+0xc34578 ||
           *reinterpret_cast<std::uintptr_t*>(node+0x48)!=component)return 5;
        auto name=reinterpret_cast<const char*>(node+0x58);
        if(!std::memchr(name,0,32))return 5;
        bool match=false;
        if(garage && std::strstr(name,"_Cop_UseKeypad_SW")) {
            const float expected[]={5.5669465f,-0.178157f,-3.9803517f};float distance=0;
            for(unsigned i=0;i<3;++i) {
                const float actual=*reinterpret_cast<float*>(node+0x22c+i*4);
                if(!std::isfinite(actual))return 5;
                const float delta=actual-expected[i];distance+=delta*delta;
            }
            match=distance<0.0025f;
        } else if(!garage && !std::strcmp(name,"MF_Switch"))match=true;
        if(match) { if(target)return 5;target=node; }
        node=*reinterpret_cast<std::uintptr_t*>(node+0x28);
    }
    if(!target)return 0;
    auto flags=reinterpret_cast<std::uint32_t*>(target+0x24c);
    constexpr std::uint32_t police=0x10004010u;
    const auto before=*flags;
    // Return to the original, live-usable generic-pad change. The custom-icon
    // experiments did not restore the visible floor graphic; remove their bit
    // and our exact injected IDs, without resetting activation or outputs.
    auto icon=reinterpret_cast<short*>(target+0x3fa);
    const auto action_icon=*reinterpret_cast<int*>(base+0x1176600);
    auto center_icon=reinterpret_cast<short*>(target+0x3fc);
    const auto after=before&~(police|0x80000000u);
    const bool injected=(before&0x80000000u) && *icon==632;
    if(injected) {
        *icon=-1;
        if(action_icon>0 && action_icon<=32767 && *center_icon==action_icon)*center_icon=-1;
    }
    if(after!=before || injected) { *flags=after;c->found=1;c->owned=1; }
    if(garage)return ResumeGarageKeypadLesson(base,owner,c);
    return 0;
}
