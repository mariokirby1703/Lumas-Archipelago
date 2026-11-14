struct TutorialStatePlan {std::uintptr_t context=0,target=0;};
static DWORD FindTutorialStatePlan(std::uintptr_t base,std::uintptr_t owner,
    const char* current_name,const char* target_name,const char* signature,TutorialStatePlan* plan) {
    const auto index=*reinterpret_cast<unsigned*>(base+0x17f8308);
    if(index>=256)return 5;
    auto jobs=*reinterpret_cast<std::uintptr_t*>(owner+0xd0+index*8);
    if(!jobs)return 0;
    if(*reinterpret_cast<std::uintptr_t*>(jobs)!=base+0xc47668)return 5;
    auto manager=jobs+0x308;
    if(*reinterpret_cast<std::uintptr_t*>(manager)!=base+0xc49038)return 5;
    auto count=*reinterpret_cast<unsigned*>(manager+0x1a8);
    auto array=*reinterpret_cast<std::uintptr_t*>(manager+0x1a0);
    if(count>128 || (count && !array))return 5;
    for(unsigned i=0;i<count;++i) {
        auto component=*reinterpret_cast<std::uintptr_t*>(array+i*8);
        if(!component || *reinterpret_cast<std::uintptr_t*>(component)!=base+0xc490a8 ||
           *reinterpret_cast<std::uintptr_t*>(component+0x18)!=manager)return 5;
        auto ctx=*reinterpret_cast<std::uintptr_t*>(component+0x38);
        if(!ctx)continue;
        if(*reinterpret_cast<std::uintptr_t*>(ctx)!=base+0xc49010)return 5;
        auto sm=*reinterpret_cast<std::uintptr_t*>(ctx+0x18);
        if(!sm || *reinterpret_cast<std::uintptr_t*>(sm+0x20)!=owner)return 5;
        if(*reinterpret_cast<unsigned char*>(ctx+0x59)!=2 ||
           *reinterpret_cast<std::uintptr_t*>(ctx+0x28))continue;
        auto frames=*reinterpret_cast<std::uintptr_t*>(ctx+0x50);
        if(!frames)return 5;
        auto frame=*reinterpret_cast<std::uintptr_t*>(frames+8);
        auto current=frame ? *reinterpret_cast<std::uintptr_t*>(frame+8) : 0;
        auto name=current ? *reinterpret_cast<const char**>(current+0x40) : nullptr;
        if(!name || !std::memchr(name,0,64))return 5;
        if(std::strcmp(name,current_name))continue;
        auto root_frame=*reinterpret_cast<std::uintptr_t*>(frames);
        auto root=root_frame ? *reinterpret_cast<std::uintptr_t*>(root_frame+8) : 0;
        if(!root)return 5;
        auto node=*reinterpret_cast<std::uintptr_t*>(root+0x20);
        std::uintptr_t target=0,visited[128]{};unsigned seen=0;bool own=false,identified=false;
        while(node) {
            if(seen>=128)return 5;
            for(unsigned j=0;j<seen;++j)if(visited[j]==node)return 5;
            visited[seen++]=node;
            auto text=*reinterpret_cast<const char**>(node+0x40);
            if(!text || !std::memchr(text,0,64))return 5;
            if(node==current)own=true;
            if(!std::strcmp(text,signature))identified=true;
            if(!std::strcmp(text,target_name)) {if(target)return 5;target=node;}
            node=*reinterpret_cast<std::uintptr_t*>(node+8);
        }
        if(!own || !identified || !target ||
           *reinterpret_cast<unsigned char*>(target+0x3a)!=5 ||
           *reinterpret_cast<unsigned char*>(target+0x3b)!=0 || plan->context)return 5;
        plan->context=ctx;plan->target=target;
    }
    return 0;
}
static DWORD FindChiefObject(std::uintptr_t base,std::uintptr_t table,unsigned index,
    std::uintptr_t manager_vt,std::uintptr_t object_vt,const char* name,std::uintptr_t* result) {
    auto manager=*reinterpret_cast<std::uintptr_t*>(table+index*8);
    if(!manager || *reinterpret_cast<std::uintptr_t*>(manager)!=base+manager_vt)return 5;
    auto node=*reinterpret_cast<std::uintptr_t*>(manager+0xe0);
    std::uintptr_t seen[256]{};unsigned count=0;
    while(node) {
        if(count>=256)return 5;
        for(unsigned i=0;i<count;++i)if(seen[i]==node)return 5;
        seen[count++]=node;
        if(*reinterpret_cast<std::uintptr_t*>(node)!=base+object_vt ||
           *reinterpret_cast<std::uintptr_t*>(node+0x48)!=manager)return 5;
        auto text=reinterpret_cast<const char*>(node+0x58);
        if(!std::memchr(text,0,32))return 5;
        if(!std::strcmp(text,name)) {if(*result)return 5;*result=node;}
        node=*reinterpret_cast<std::uintptr_t*>(node+0x28);
    }
    return 0;
}
static DWORD UnlockChiefKey(std::uintptr_t base,std::uintptr_t actor,Command* c) {
    if(c->model || c->name_hash!=Hash("CHIEF_KEY"))return 6;
    c->found=0;c->owned=0;
    auto acquired=LobbyField(base,"PDA","acquired",0xc46bb8);
    auto synced=LobbyField(base,"PDA","synchronised",0xc46bb8);
    auto act=LobbyField(base,"Flow_Setup","Flow_Act",0xc46b38);
    auto mission=LobbyField(base,"Flow_Setup.Act_1","Act1_Mission",0xc46b38);
    auto stage=LobbyField(base,"Flow_Setup.Act_1","Act1_Stage",0xc46b38);
    if(!acquired || !synced || !act || !mission || !stage ||
       *reinterpret_cast<unsigned char*>(acquired+16)!=1 ||
       *reinterpret_cast<unsigned char*>(synced+16)!=1 ||
       *reinterpret_cast<int*>(act+16)!=1 || *reinterpret_cast<int*>(mission+16)!=1 ||
       *reinterpret_cast<int*>(stage+16)!=2)return 0;
    auto registry=*reinterpret_cast<std::uintptr_t*>(base+0x1c402d8);
    auto index=*reinterpret_cast<unsigned short*>(actor+0x28);
    if(!registry || index>0x7ff)return 5;
    auto entry=*reinterpret_cast<std::uintptr_t*>(registry+0x18+index*8);
    auto owner=entry ? *reinterpret_cast<std::uintptr_t*>(entry+0xd8) : 0;
    auto tile=owner ? *reinterpret_cast<std::uintptr_t*>(owner+0xb18) : 0;
    auto name=tile ? *reinterpret_cast<const char**>(tile+0x68) : nullptr;
    if(!name || Hash(name)!=Hash("POLICE_STATION_LOBBY"))return 0;
    TutorialStatePlan lobby,scan;
    auto error=FindTutorialStatePlan(base,owner,"DetectiveHint","WaitForChiefLock","ChiefAwakesMinicut",&lobby);
    if(error)return error;
    if(!lobby.context) {
        error=FindTutorialStatePlan(base,owner,"WaitForDspot","WaitForChiefLock","ChiefAwakesMinicut",&lobby);
        if(error)return error;
    }
    if(!lobby.context)return 0;
    error=FindTutorialStatePlan(base,owner,"FirstJunction","Ended","Key_PickedUp",&scan);
    if(error)return error;
    if(!scan.context)return 0;
    auto level=*reinterpret_cast<std::uintptr_t*>(owner+0xbb0);
    auto data=level ? *reinterpret_cast<std::uintptr_t*>(level+0xa0) : 0;
    auto table=data ? *reinterpret_cast<std::uintptr_t*>(data+0xc0) : 0;
    if(!table)return 5;
    std::uintptr_t key=0,lock=0;
    error=FindChiefObject(base,table,5,0xc2b878,0xd748c8,"M02_Dspot_key_item",&key);
    if(error)return error;
    error=FindChiefObject(base,table,28,0xc36198,0xc35a98,"Story_02_LobbyLock",&lock);
    if(error)return error;
    if(!key || !lock)return 5;
    float distance=0;
    for(unsigned i=0;i<3;++i) {
        float a=*reinterpret_cast<float*>(actor+0x1f0+i*4),b=*reinterpret_cast<float*>(lock+0x78+i*4);
        if(!std::isfinite(a) || !std::isfinite(b))return 5;
        float d=a-b;distance+=d*d;
    }
    if(distance>2.25f)return 0;
    if(*reinterpret_cast<std::uintptr_t*>(key+0x108)!=base+0xc1ba18)return 5;
    const unsigned char active_prefix[]={0x48,0x89,0x5c,0x24,0x08,0x57,0x48,0x83,0xec,0x20};
    const unsigned char goto_prefix[]={0x48,0x89,0x5c,0x24,0x08,0x48,0x89,0x74,0x24,0x10};
    if(std::memcmp(reinterpret_cast<void*>(base+0x77d3e0),active_prefix,sizeof(active_prefix)) ||
       std::memcmp(reinterpret_cast<void*>(base+0x653b60),goto_prefix,sizeof(goto_prefix)))return 1;
    // Enable the pre-existing item at its original position. End the detective
    // tutorial and enter the original key-found stage; the player still picks
    // up the key and operates the real lock. No skill entitlement or check bit.
    reinterpret_cast<void(*)(void*,int,bool)>(base+0x77d3e0)(reinterpret_cast<void*>(key+0x108),1,true);
    auto go=reinterpret_cast<void(*)(std::uintptr_t,int,std::uintptr_t)>(base+0x653b60);
    go(scan.context,-1,scan.target);go(lobby.context,-1,lobby.target);
    c->found=1;c->owned=1;return 0;
}
static DWORD RevealChiefRadio(std::uintptr_t base,std::uintptr_t actor,Command* c) {
    if(c->model || c->name_hash!=Hash("CHIEF_RADIO"))return 6;
    c->found=0;c->owned=0;
    auto synced=LobbyField(base,"PDA","synchronised",0xc46bb8);
    if(!synced || *reinterpret_cast<unsigned char*>(synced+16)!=1)return 0;
    auto registry=*reinterpret_cast<std::uintptr_t*>(base+0x1c402d8);
    auto index=*reinterpret_cast<unsigned short*>(actor+0x28);
    if(!registry || index>0x7ff)return 5;
    auto entry=*reinterpret_cast<std::uintptr_t*>(registry+0x18+index*8);
    auto owner=entry ? *reinterpret_cast<std::uintptr_t*>(entry+0xd8) : 0;
    auto tile=owner ? *reinterpret_cast<std::uintptr_t*>(owner+0xb18) : 0;
    auto name=tile ? *reinterpret_cast<const char**>(tile+0x68) : nullptr;
    if(!name || Hash(name)!=Hash("POLICE_STATION_LOBBY"))return 0;
    TutorialStatePlan waiting;
    auto error=FindTutorialStatePlan(base,owner,"WaitForRadioBuildit","ChiefAwakesMinicut","WaitForChiefLock",&waiting);
    if(error || !waiting.context)return error;
    auto level=*reinterpret_cast<std::uintptr_t*>(owner+0xbb0);
    auto data=level ? *reinterpret_cast<std::uintptr_t*>(level+0xa0) : 0;
    auto table=data ? *reinterpret_cast<std::uintptr_t*>(data+0xc0) : 0;
    if(!table)return 5;
    std::uintptr_t build=0;
    error=FindChiefObject(base,table,3,0xd769c8,0xd76478,"RadioBuildit",&build);
    if(error)return error;
    if(!build)return 5;
    float distance=0;
    for(unsigned i=0;i<3;++i) {
        float a=*reinterpret_cast<float*>(actor+0x1f0+i*4),b=*reinterpret_cast<float*>(build+0x78+i*4);
        if(!std::isfinite(a) || !std::isfinite(b))return 5;
        float d=a-b;distance+=d*d;
    }
    if(distance>4.0f || (*reinterpret_cast<unsigned short*>(build+0x8a)&3)==3)return 0;
    if(*reinterpret_cast<std::uintptr_t*>(build+0x108)!=base+0xc1ba18)return 5;
    const unsigned char prefix[]={0x48,0x89,0x5c,0x24,0x08,0x57,0x48,0x83,0xec,0x20};
    if(std::memcmp(reinterpret_cast<void*>(base+0x77d3e0),prefix,sizeof(prefix)))return 1;
    reinterpret_cast<void(*)(void*,int,bool)>(base+0x77d3e0)(reinterpret_cast<void*>(build+0x108),1,true);
    c->found=1;c->owned=1;return 0;
}
