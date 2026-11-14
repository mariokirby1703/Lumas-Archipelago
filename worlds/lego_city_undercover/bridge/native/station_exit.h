// Existing door transition with a guarded pre-tutorial re-entry value.
#include "lobby_resume.h"
static DWORD TriggerStationExit(std::uintptr_t base,std::uintptr_t actor,Command* c) {
    if(c->model || c->name_hash!=Hash("STATION_EXIT"))return 6;
    c->found=0;c->owned=0;
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
    if(garage) {
        auto bank=*reinterpret_cast<std::uintptr_t*>(base+0x1c7cbb8);
        if(!bank)return 4;
        // Once Police is owned, leave the normal garage tutorial path in charge.
        if(*reinterpret_cast<unsigned char*>(bank+0x80+227))return 0;
    }
    const char* door_name=garage ? "POLICE_GARAGE_DOOR" : "POLICE_LOBBY_EXTERNAL_DOOR";
    auto level=*reinterpret_cast<std::uintptr_t*>(owner+0xbb0);
    if(!level)return 4;
    auto data=*reinterpret_cast<std::uintptr_t*>(level+0xa0);
    if(!data)return 4;
    auto table=*reinterpret_cast<std::uintptr_t*>(data+0xc0);
    if(!table)return 4;
    auto manager=*reinterpret_cast<std::uintptr_t*>(table+18*8);
    if(!manager || *reinterpret_cast<std::uintptr_t*>(manager)!=base+0xd603f8)return 5;
    auto node=*reinterpret_cast<std::uintptr_t*>(manager+0xe0);
    std::uintptr_t target=0,visited[64]{};unsigned count=0;
    while(node) {
        if(count>=64)return 5;
        for(unsigned i=0;i<count;++i)if(visited[i]==node)return 5;
        visited[count++]=node;
        if(*reinterpret_cast<std::uintptr_t*>(node)!=base+0xd5fc98 ||
           *reinterpret_cast<std::uintptr_t*>(node+0x48)!=manager)return 5;
        const auto name=reinterpret_cast<const char*>(node+0x58);
        if(!std::memchr(name,0,32))return 5;
        if(!std::strcmp(name,door_name)) {
            if(target)return 5;target=node;
        }
        node=*reinterpret_cast<std::uintptr_t*>(node+0x28);
    }
    if(!target)return 4;
    if(*reinterpret_cast<std::uintptr_t*>(*reinterpret_cast<std::uintptr_t*>(actor+0x10)+0xf0)!=base+0x49ecf0)return 5;
    float distance=0;
    for(unsigned i=0;i<3;++i) {
        const float a=*reinterpret_cast<float*>(actor+0x1f0+i*4);
        // Put the garage trigger in front of its closed lift collision plane.
        const float b=*reinterpret_cast<float*>(target+0x78+i*4)+((garage && i==0) ? -0.6f : 0.0f);
        if(!std::isfinite(a) || !std::isfinite(b))return 5;
        const float delta=a-b;distance+=delta*delta;
    }
    if(distance>0.64f)return 0; // Match the host's 0.8 m doorway radius.
    auto vtable=*reinterpret_cast<std::uintptr_t*>(target);
    if(*reinterpret_cast<std::uintptr_t*>(vtable+0x210)!=base+0x8a1780)return 1;
    const unsigned char trigger_prefix[]={0x40,0x53,0x48,0x83,0xec,0x30};
    if(std::memcmp(reinterpret_cast<void*>(base+0x8a1780),trigger_prefix,sizeof(trigger_prefix)))return 1;
    auto resume=EarlyLobbyResumeCounter(base);
    if(!resume)return 16;
    // JobValueInt::Assign (0xda1b0) stores this same +0x10 field without
    // additional callbacks. Preserve this exact phase on the next entry.
    // No mission completion, class entitlement or mainframe flag is changed.
    *resume=0;
    using Trigger=void(*)(void*);
    reinterpret_cast<Trigger>(base+0x8a1780)(reinterpret_cast<void*>(target));
    c->found=1;c->owned=1;return 0;
}
