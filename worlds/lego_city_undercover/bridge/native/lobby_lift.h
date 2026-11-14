// Reuse the exact two animation gizmos used by LCPD_LobbySecond's lift arrival.
// This opens collision/animation only; it does not start that tutorial script.
static DWORD OpenLobbyLift(std::uintptr_t base,std::uintptr_t actor,Command* c) {
    if(c->model || c->name_hash!=Hash("OPEN_LOBBY_LIFT"))return 6;
    c->found=0;c->owned=0;
    auto resume=EarlyLobbyResumeCounter(base);
    if(!resume || *resume!=1)return 16;
    auto registry=*reinterpret_cast<std::uintptr_t*>(base+0x1c402d8);
    const auto index=*reinterpret_cast<unsigned short*>(actor+0x28);
    if(!registry || index>0x7ff)return 5;
    auto entry=*reinterpret_cast<std::uintptr_t*>(registry+0x18+index*8);
    if(!entry)return 4;
    auto owner=*reinterpret_cast<std::uintptr_t*>(entry+0xd8);
    if(!owner)return 4;
    auto tile=*reinterpret_cast<std::uintptr_t*>(owner+0xb18);
    if(!tile)return 4;
    auto scene=*reinterpret_cast<const char**>(tile+0x68);
    if(!scene || Hash(scene)!=Hash("POLICE_STATION_LOBBY"))return 0;
    auto level=*reinterpret_cast<std::uintptr_t*>(owner+0xbb0);
    if(!level)return 4;
    auto data=*reinterpret_cast<std::uintptr_t*>(level+0xa0);
    if(!data)return 4;
    auto table=*reinterpret_cast<std::uintptr_t*>(data+0xc0);
    if(!table)return 4;
    auto manager=*reinterpret_cast<std::uintptr_t*>(table+8);
    if(!manager || *reinterpret_cast<std::uintptr_t*>(manager)!=base+0xc2e468)return 5;
    auto node=*reinterpret_cast<std::uintptr_t*>(manager+0xe0);
    std::uintptr_t opening=0,closing=0,visited[256]{};unsigned count=0;
    while(node) {
        if(count>=256)return 5;
        for(unsigned i=0;i<count;++i)if(visited[i]==node)return 5;
        visited[count++]=node;
        if(*reinterpret_cast<std::uintptr_t*>(node)!=base+0xc2dec8 ||
           *reinterpret_cast<std::uintptr_t*>(node+0x48)!=manager)return 5;
        auto name=reinterpret_cast<const char*>(node+0x58);
        if(!std::memchr(name,0,32))return 5;
        if(!std::strcmp(name,"DoorsOpening")) { if(opening)return 5;opening=node; }
        if(!std::strcmp(name,"DoorsClosing")) { if(closing)return 5;closing=node; }
        node=*reinterpret_cast<std::uintptr_t*>(node+0x28);
    }
    if(!opening || !closing)return 4;
    if(*reinterpret_cast<std::uintptr_t*>(opening+0x108)!=base+0xc1ba18 ||
       *reinterpret_cast<std::uintptr_t*>(closing+0x108)!=base+0xc1ba18)return 5;
    if(*reinterpret_cast<std::uintptr_t*>(*reinterpret_cast<std::uintptr_t*>(actor+0x10)+0xf0)!=base+0x49ecf0)return 5;
    float distance=0;
    for(unsigned i=0;i<3;++i) {
        const float a=*reinterpret_cast<float*>(actor+0x1f0+i*4);
        const float b=*reinterpret_cast<float*>(opening+0x78+i*4);
        if(!std::isfinite(a) || !std::isfinite(b))return 5;
        distance+=(a-b)*(a-b);
    }
    if(distance>2.25f)return 0;
    // GizmoAction_SetActive (0x9e83a0) calls this exact flow-interface setter.
    const unsigned char prefix[]={0x48,0x89,0x5c,0x24,0x08,0x57,0x48,0x83,0xec,0x20};
    if(std::memcmp(reinterpret_cast<void*>(base+0x77d3e0),prefix,sizeof(prefix)))return 1;
    using SetActive=void(*)(void*,int,bool);
    auto active=reinterpret_cast<SetActive>(base+0x77d3e0);
    active(reinterpret_cast<void*>(closing+0x108),0,true);
    active(reinterpret_cast<void*>(opening+0x108),1,true);
    c->found=1;c->owned=1;return 0;
}
