// Enable the original city job tree when AP has granted SuperBuild.
// lcu.lego_city.jobleveltree explicitly ORs this persistent flag with story stage.
// Do not synthesize nState, Completed, rewards or story mission progression.
static DWORD EnableSuperbuildJobs(std::uintptr_t base,Command* c) {
    if(c->model || c->name_hash!=Hash("SUPERBUILD_JOBS") ||
       !(c->binding[0]|c->binding[1]|c->binding[2]|c->binding[3]))return 6;
    c->found=0;c->owned=0;
    auto profile=*reinterpret_cast<std::uintptr_t*>(base+0x1c7f160);
    auto bank=*reinterpret_cast<std::uintptr_t*>(base+0x1c7cbb8);
    auto abilities=*reinterpret_cast<std::uintptr_t*>(base+0x17ebd48);
    if(!profile || !bank || !abilities || bank!=profile+0x122e0)return 4;
    auto marker=reinterpret_cast<unsigned char*>(bank+0x80+1002);
    bool empty=true;for(unsigned i=0;i<22;++i)empty=empty && marker[i]==0;
    if(!empty && (marker[0]!='A' || marker[1]!='P' || std::memcmp(marker+2,c->binding,16)))return 13;
    const auto unlocked=*reinterpret_cast<unsigned char*>(abilities+0xd8+2);
    const auto pending=*reinterpret_cast<unsigned char*>(abilities+0x10b+2);
    if(unlocked>1 || pending>1)return 5;
    if(!unlocked && !pending)return 0;
    auto field=LobbyField(base,"SuperBuild_Saves","SuperBuildsActive",0xc46bb8);
    auto maximum=LobbyField(base,"SuperBuild_Saves","Max_Completed",0xc46b38);
    if(!field || !maximum || *reinterpret_cast<int*>(maximum+16)!=65)return 5;
    auto active=reinterpret_cast<unsigned char*>(field+16);
    if(*active>1)return 5;
    if(!*active) { *active=1;c->found=1; }
    c->owned=*active==1;return c->owned ? 0 : 7;
}
