// Executed only through the pinned item bridge on the game window thread.
struct RewardPolicy {
    std::uint32_t magic,version,pid,reserved;
    std::uint32_t managed_models[32],entitled_models[32];
    std::uint64_t managed_abilities,entitled_abilities,managed_cheats,entitled_cheats;
    std::uint32_t binding[4];
};
static_assert(sizeof(RewardPolicy)==320);
static bool Denies(const RewardPolicy& p,int model) {
    return model>=0 && model<1002 &&
        (p.managed_models[model/32] & ~p.entitled_models[model/32] & (1u<<(model%32)));
}
static DWORD EnforceRewards(std::uintptr_t base,std::uintptr_t actor,Command* c,bool dry_run=false) {
    if(c->model || Hash("ENFORCE_POLICY")!=c->name_hash)return 6;
    wchar_t name[80]{};
    swprintf(name,80,L"Local\\LCURewardPolicy_%lu",GetCurrentProcessId());
    HANDLE mapping=OpenFileMappingW(FILE_MAP_READ,FALSE,name);
    if(!mapping)return 15;
    auto view=MapViewOfFile(mapping,FILE_MAP_READ,0,0,sizeof(RewardPolicy));
    if(!view) { CloseHandle(mapping);return 15; }
    RewardPolicy p{};std::memcpy(&p,view,sizeof(p));UnmapViewOfFile(view);CloseHandle(mapping);
    if(p.magic!=0x4c435550 || p.version!=1 || p.pid!=GetCurrentProcessId() || p.reserved ||
       std::memcmp(p.binding,c->binding,16))return 6;
    for(unsigned i=0;i<32;++i)
        if(p.entitled_models[i]&~p.managed_models[i])return 9;
    if((p.managed_models[31]&0xfffffc00u) || (p.managed_abilities>>51) ||
       (p.managed_cheats>>40) || (p.entitled_abilities&~p.managed_abilities) ||
       (p.entitled_cheats&~p.managed_cheats))return 9;
    auto models=*reinterpret_cast<std::uintptr_t*>(base+0x17ebd38);
    auto bank=*reinterpret_cast<std::uintptr_t*>(base+0x1c7cbb8);
    auto controller=*reinterpret_cast<std::uintptr_t*>(base+0x17ebe20);
    auto abilities=*reinterpret_cast<std::uintptr_t*>(base+0x17ebd48);
    auto cheats=*reinterpret_cast<std::uintptr_t*>(base+0x11755f8);
    auto cheat_owned=*reinterpret_cast<std::uint64_t**>(base+0x1c7e850);
    auto profile=*reinterpret_cast<std::uintptr_t*>(base+0x1c7f160);
    if(!models || !bank || !controller || !abilities || !cheats || !cheat_owned || !profile)return 4;
    if(bank!=profile+0x122e0 || reinterpret_cast<std::uintptr_t>(cheat_owned)!=profile+0xfa80)return 5;
    if(*reinterpret_cast<std::uint32_t*>(models+0xe0)!=1002 ||
       *reinterpret_cast<std::uint32_t*>(cheats+8)!=40)return 5;
    auto table=*reinterpret_cast<std::uintptr_t*>(models+0x118);
    auto cheat_table=*reinterpret_cast<std::uintptr_t*>(cheats);
    if(!table || !cheat_table)return 4;
    // The two starting civilians stay usable even if their cosmetic items exist.
    int fallback=-1;
    for(int i=0;i<1002;++i) {
        auto record=*reinterpret_cast<std::uintptr_t*>(table+i*8);
        if(!record)continue;
        auto model_name=*reinterpret_cast<const char**>(record+0x30);
        if(!model_name)continue;
        const auto hash=Hash(model_name);
        if(hash==Hash("CIVILIAN_CHASEMCCAIN") || hash==Hash("CIVILIAN_CHASEMCCAIN_ALT")) {
            if(Denies(p,i))return 9;
            if(hash==Hash("CIVILIAN_CHASEMCCAIN"))fallback=i;
        }
    }
    if(fallback<0)return 5;
    const auto extra_count=*reinterpret_cast<std::uint32_t*>(controller+0x1ac);
    auto extra=*reinterpret_cast<short**>(controller+0x1a0);
    if(extra_count>128 || (extra_count && !extra))return 5;
    const unsigned char lock_prefix[]={0x48,0x83,0xec,0x48};
    const unsigned char save_prefix[]={0x80,0x79,0x21,0};
    if(std::memcmp(reinterpret_cast<void*>(base+0x90c80),lock_prefix,sizeof(lock_prefix)) ||
       std::memcmp(reinterpret_cast<void*>(base+0xd18b0),save_prefix,sizeof(save_prefix)))return 1;
    auto actor_model=*reinterpret_cast<std::uintptr_t*>(actor+0x650);
    if(!actor_model)return 4;
    const int current=*reinterpret_cast<short*>(actor_model+8);
    if(current<0 || current>=1002)return 5;
    if(dry_run) {
        unsigned changes=0;
        for(int i=0;i<1002;++i)
            if(Denies(p,i) && *reinterpret_cast<unsigned char*>(bank+0x80+i))++changes;
        c->found=changes;c->owned=Denies(p,current) ? 2 : 0;return 0;
    }
    if(!InstallShopGuards(base,p.managed_models) || !InstallCategoryGuard(base))return 1;
    if(Denies(p,current)) {
        // Never replace or revoke the actor underneath an active interaction.
        // The user must select an entitled outfit before deferred revocation.
        c->found=0;c->owned=2;return 0;
    }
    unsigned changed=0;
    using Discover=void(*)(void*,int);
    auto found=reinterpret_cast<Discover>(base+0x88a2b0);
    auto state=reinterpret_cast<unsigned char*>(bank);
    auto preserve_source=[&](int model) {
        if(!(state[model/8]&(1u<<(model%8))))found(state,model);
    };
    auto pending=reinterpret_cast<short*>(controller+0x16a);
    for(unsigned i=0;i<16;++i)if(Denies(p,pending[i])) {
        preserve_source(pending[i]);pending[i]=-1;
        *reinterpret_cast<unsigned char*>(controller+0x18a+i)=0;++changed;
    }
    unsigned kept=0;
    for(unsigned i=0;i<extra_count;++i) {
        if(Denies(p,extra[i])) { preserve_source(extra[i]);++changed; }
        else extra[kept++]=extra[i];
    }
    if(kept!=extra_count)*reinterpret_cast<std::uint32_t*>(controller+0x1ac)=kept;
    for(int i=0;i<1002;++i)if(Denies(p,i) && state[0x80+i]) {
        state[0x80+i]=0;++changed;
    }
    using Lock=void(*)(void*,unsigned char*);
    const auto blocked=p.managed_abilities&~p.entitled_abilities;
    for(unsigned char i=0;i<51;++i)if(blocked&(std::uint64_t(1)<<i)) {
        if(*reinterpret_cast<unsigned char*>(abilities+0xd8+i) ||
           *reinterpret_cast<unsigned char*>(abilities+0x10b+i)) {
            reinterpret_cast<Lock>(base+0x90c80)(reinterpret_cast<void*>(abilities),&i);++changed;
        }
    }
    const auto blocked_cheats=p.managed_cheats&~p.entitled_cheats;
    for(unsigned i=0;i<40;++i)if(blocked_cheats&(std::uint64_t(1)<<i)) {
        auto active=reinterpret_cast<unsigned char*>(cheat_table+i*32+0x1a);
        if(*active || (*cheat_owned&(std::uint64_t(1)<<i))) {
            *active=0;*cheat_owned&=~(std::uint64_t(1)<<i);
            ++changed;
        }
    }
    if(changed) {
        auto stats=*reinterpret_cast<std::uintptr_t*>(base+0x1c7a830);
        if(stats && *reinterpret_cast<unsigned char*>(stats+0x3638+0x21)) {
            using Save=void(*)(void*);
            reinterpret_cast<Save>(base+0xd18b0)(reinterpret_cast<void*>(stats+0x3638));
        }
    }
    c->found=changed;c->owned=changed ? 1 : 0;return 0;
}
