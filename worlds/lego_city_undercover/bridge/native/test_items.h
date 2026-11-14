// Explicit local test edits, never receipt/collection-marker edits.
static DWORD TestCurrency(std::uintptr_t base,Command* c) {
    const bool studs=c->name_hash==Hash("TEST_ADD_STUDS") || c->name_hash==Hash("TEST_REMOVE_STUDS");
    const bool bricks=c->name_hash==Hash("TEST_ADD_BRICKS") || c->name_hash==Hash("TEST_REMOVE_BRICKS");
    const bool remove=c->name_hash==Hash("TEST_REMOVE_STUDS") || c->name_hash==Hash("TEST_REMOVE_BRICKS");
    if(!studs && !bricks)return 6;
    auto amount=c->model;
    if(studs ? (amount!=1000 && amount!=10000 && amount!=100000) :
               (amount!=100 && amount!=250 && amount!=1000 && amount!=10000))return 9;
    auto profile=*reinterpret_cast<std::uintptr_t*>(base+0x1c7f160);
    auto stats=*reinterpret_cast<std::uintptr_t*>(base+0x1c7a830);
    if(!profile || !stats)return 4;
    if(studs) {
        auto value=reinterpret_cast<std::uint64_t*>(profile+0xfb10);
        if(remove ? *value<amount : *value>UINT64_MAX-amount)return 12;
        *value=remove ? *value-amount : *value+amount;
    } else {
        const unsigned char prefix[]={0x80,0xb9,0x5d,0x33,0,0,0};
        if(std::memcmp(reinterpret_cast<void*>(base+0x3bf70),prefix,sizeof(prefix)) ||
           std::memcmp(reinterpret_cast<void*>(base+0x40e30),prefix,sizeof(prefix)))return 1;
        auto get=reinterpret_cast<std::uint32_t(*)(void*)>(base+0x3bf70);
        auto set=reinterpret_cast<void(*)(void*,std::uint32_t)>(base+0x40e30);
        auto value=get(reinterpret_cast<void*>(stats));
        if(remove ? value<amount : value>INT32_MAX-amount)return 12;
        set(reinterpret_cast<void*>(stats),remove ? value-amount : value+amount);
    }
    c->found=1;c->owned=1;return 0;
}
static DWORD TestRemove(std::uintptr_t base,std::uintptr_t actor,Command* c) {
    if(c->receipt==1) {
        auto manager=*reinterpret_cast<std::uintptr_t*>(base+0x17ebd38);
        auto bank=*reinterpret_cast<std::uintptr_t*>(base+0x1c7cbb8);
        auto controller=*reinterpret_cast<std::uintptr_t*>(base+0x17ebe20);
        if(!manager || !bank || !controller)return 4;
        if(c->model>=1002 || *reinterpret_cast<unsigned*>(manager+0xe0)!=1002)return 5;
        auto table=*reinterpret_cast<std::uintptr_t*>(manager+0x118);
        auto record=table ? *reinterpret_cast<std::uintptr_t*>(table+c->model*8) : 0;
        auto name=record ? *reinterpret_cast<const char**>(record+0x30) : nullptr;
        if(!name || Hash(name)!=c->name_hash)return 6;
        if(Hash(name)==Hash("CIVILIAN_CHASEMCCAIN") || Hash(name)==Hash("CIVILIAN_CHASEMCCAIN_ALT"))return 19;
        auto model=*reinterpret_cast<std::uintptr_t*>(actor+0x650);
        if(!model || *reinterpret_cast<short*>(model+8)==c->model)return 19;
        auto count=*reinterpret_cast<unsigned*>(controller+0x1ac);
        if(count>1002)return 5;
        auto extra=*reinterpret_cast<short**>(controller+0x1a0);
        if(count && !extra)return 5;
        auto pending=reinterpret_cast<short*>(controller+0x16a);
        for(unsigned i=0;i<16;++i)if(pending[i]==c->model) {
            pending[i]=-1;*reinterpret_cast<unsigned char*>(controller+0x18a+i)=0;
        }
        unsigned kept=0;
        for(unsigned i=0;i<count;++i)if(extra[i]!=c->model)extra[kept++]=extra[i];
        *reinterpret_cast<unsigned*>(controller+0x1ac)=kept;
        *reinterpret_cast<unsigned char*>(bank+0x80+c->model)=0;
        // Genuine found/source bits are intentionally untouched.
    } else if(c->receipt==2) {
        static const unsigned ids[]={0,1,2,3,4,5,6,7,8,10,11,12,13,14,18,19,20,21,46,47,48,50};
        static const char* names[]={"GrappleGun","EnergyGun","SuperBuild","Parkour","Grab","TargetThrow","FinishingMove","Parry","Scanner","Camera","Surveillance","Wiretap","DataScanner","Snapshot","Jetpack","FireAxe","Pigs","FastTravel","DisguiseBooth","Race","SuperStrength","2x_Brick_Multi"};
        bool valid=false;for(unsigned i=0;i<22;++i)if(c->model==ids[i] && c->name_hash==Hash(names[i]))valid=true;
        if(!valid)return 9;
        auto manager=*reinterpret_cast<std::uintptr_t*>(base+0x17ebd48);if(!manager)return 4;
        const unsigned char prefix[]={0x48,0x83,0xec,0x48};
        if(std::memcmp(reinterpret_cast<void*>(base+0x90c80),prefix,sizeof(prefix)))return 1;
        auto id=static_cast<unsigned char>(c->model);
        reinterpret_cast<void(*)(void*,unsigned char*)>(base+0x90c80)(reinterpret_cast<void*>(manager),&id);
    } else if(c->receipt==3) {
        auto manager=*reinterpret_cast<std::uintptr_t*>(base+0x11755f8);
        auto effect=*reinterpret_cast<std::uint64_t**>(base+0x1c7e850);
        if(!manager || !effect)return 4;
        if(c->model>=40 || *reinterpret_cast<unsigned*>(manager+8)!=40)return 5;
        auto table=*reinterpret_cast<std::uintptr_t*>(manager);
        auto definition=table ? *reinterpret_cast<std::uintptr_t*>(table+c->model*32) : 0;
        auto name=definition ? *reinterpret_cast<const char**>(definition) : nullptr;
        if(!name || Hash(name)!=c->name_hash)return 6;
        *reinterpret_cast<unsigned char*>(table+c->model*32+0x1a)=0;
        *effect&=~(std::uint64_t(1)<<c->model);
    } else return 9;
    c->found=1;c->owned=1;return 0;
}
