// Replace only the garage's outfit-equipping lesson. The next original state
// still waits for iKEYPAD_USE_OFF_CMPLX.GetOutput(0), so no keypad use is forged.
static DWORD ResumeGarageKeypadLesson(std::uintptr_t base,std::uintptr_t owner,Command* c) {
    const auto index=*reinterpret_cast<unsigned*>(base+0x17f8308);
    if(index>=256)return 5;
    auto jobs=*reinterpret_cast<std::uintptr_t*>(owner+0xd0+index*8);
    if(!jobs)return 0;
    if(*reinterpret_cast<std::uintptr_t*>(jobs)!=base+0xc47668)return 5;
    auto manager=jobs+0x308;
    if(*reinterpret_cast<std::uintptr_t*>(manager)!=base+0xc49038)return 5;
    const auto count=*reinterpret_cast<unsigned*>(manager+0x1a8);
    auto components=*reinterpret_cast<std::uintptr_t*>(manager+0x1a0);
    if(count>128 || (count && !components))return 5;
    std::uintptr_t selected=0,destination=0;
    for(unsigned i=0;i<count;++i) {
        auto component=*reinterpret_cast<std::uintptr_t*>(components+i*8);
        if(!component || *reinterpret_cast<std::uintptr_t*>(component)!=base+0xc490a8 ||
           *reinterpret_cast<std::uintptr_t*>(component+0x18)!=manager)return 5;
        auto context=*reinterpret_cast<std::uintptr_t*>(component+0x38);
        if(!context)continue;
        if(*reinterpret_cast<std::uintptr_t*>(context)!=base+0xc49010)return 5;
        auto script_manager=*reinterpret_cast<std::uintptr_t*>(context+0x18);
        if(!script_manager || *reinterpret_cast<std::uintptr_t*>(script_manager+0x20)!=owner)return 5;
        // Only an idle top-level state, never a nested callback or pending goto.
        if(*reinterpret_cast<unsigned char*>(context+0x59)!=2 ||
           *reinterpret_cast<std::uintptr_t*>(context+0x28))continue;
        auto frames=*reinterpret_cast<std::uintptr_t*>(context+0x50);
        if(!frames)return 5;
        auto frame=*reinterpret_cast<std::uintptr_t*>(frames+8);
        auto current=frame ? *reinterpret_cast<std::uintptr_t*>(frame+8) : 0;
        auto name=current ? *reinterpret_cast<const char**>(current+0x40) : nullptr;
        if(!name || !std::memchr(name,0,64))return 5;
        if(std::strcmp(name,"LoopChangeClothesHint"))continue;
        auto root_frame=*reinterpret_cast<std::uintptr_t*>(frames);
        auto root=root_frame ? *reinterpret_cast<std::uintptr_t*>(root_frame+8) : 0;
        if(!root)return 5;
        auto node=*reinterpret_cast<std::uintptr_t*>(root+0x20);
        std::uintptr_t target=0,visited[128]{};unsigned seen=0;bool current_found=false,finish=false;
        while(node) {
            if(seen>=128)return 5;
            for(unsigned j=0;j<seen;++j)if(visited[j]==node)return 5;
            visited[seen++]=node;
            auto state_name=*reinterpret_cast<const char**>(node+0x40);
            if(!state_name || !std::memchr(state_name,0,64))return 5;
            if(node==current)current_found=true;
            if(!std::strcmp(state_name,"ActivateLiftDoors"))finish=true;
            if(!std::strcmp(state_name,"ShowCostumeWheelHint")) {
                if(target)return 5;
                target=node;
            }
            node=*reinterpret_cast<std::uintptr_t*>(node+8);
        }
        if(!target || !current_found || !finish ||
           *reinterpret_cast<unsigned char*>(target+0x3a)!=5 ||
           *reinterpret_cast<unsigned char*>(target+0x3b)!=0)return 5;
        if(selected)return 5;
        selected=context;destination=target;
    }
    if(!selected)return 0;
    // Same native scheduling method as SAction_GotoState; target scope-pop is 0.
    const unsigned char prefix[]={0x48,0x89,0x5c,0x24,0x08,0x48,0x89,0x74,0x24,0x10};
    if(std::memcmp(reinterpret_cast<void*>(base+0x653b60),prefix,sizeof(prefix)))return 1;
    auto player_system=*reinterpret_cast<std::uintptr_t*>(base+0x1c7a830);
    if(!player_system)return 5;
    reinterpret_cast<void(*)(std::uintptr_t,int,std::uintptr_t)>(base+0x653b60)(selected,-1,destination);
    // Original successful condition also calls AllowCharacterSwap(true), P1.
    *reinterpret_cast<unsigned char*>(base+0xffdfdc)=1;
    if(!*reinterpret_cast<unsigned char*>(player_system+0x335e))
        *reinterpret_cast<unsigned char*>(base+0x17fe374)=0;
    ++c->found;c->owned=1;
    return 0;
}
