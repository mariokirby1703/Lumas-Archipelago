// The early lobby script interprets visit count 1 as "returned from garage".
// Preserve the first-visit setup, including after its mainframe repair.
static std::uintptr_t LobbyField(std::uintptr_t base,const char* job,const char* field,std::uintptr_t type) {
    auto system=*reinterpret_cast<std::uintptr_t*>(base+0x17eca08);
    if(!system)return 0;
    auto table=*reinterpret_cast<std::uintptr_t*>(system+0xe0);
    auto count=*reinterpret_cast<std::uint32_t*>(system+0xe8);
    if(!table || count>4096)return 0;
    std::uintptr_t result=0;unsigned matching_jobs=0;
    for(unsigned i=0;i<count;++i) {
        auto record=table+i*24;
        if(*reinterpret_cast<std::uint32_t*>(record)!=Hash(job))continue;
        if(++matching_jobs!=1)return 0;
        auto fields=*reinterpret_cast<std::uintptr_t*>(record+8);
        auto length=*reinterpret_cast<unsigned short*>(record+16);
        if(length>128 || (length && !fields))return 0;
        for(unsigned j=0;j<length;++j) {
            auto value=*reinterpret_cast<std::uintptr_t*>(fields+j*8);
            if(!value)return 0;
            if(*reinterpret_cast<std::uint32_t*>(value+12)!=Hash(field))continue;
            if(result || *reinterpret_cast<std::uintptr_t*>(value)!=base+type)return 0;
            result=value;
        }
    }
    return result;
}
static int* EarlyLobbyResumeCounter(std::uintptr_t base) {
    // After Ellie's actual basement completion the next visit MUST use
    // LobbySecond. Never reset its selector back to LobbyFirst again.
    auto acquired=LobbyField(base,"PDA","acquired",0xc46bb8);
    if(!acquired || *reinterpret_cast<unsigned char*>(acquired+16)!=0)return nullptr;
    auto act=LobbyField(base,"Flow_Setup","Flow_Act",0xc46b38);
    auto mission=LobbyField(base,"Flow_Setup.Act_1","Act1_Mission",0xc46b38);
    auto stage=LobbyField(base,"Flow_Setup.Act_1","Act1_Stage",0xc46b38);
    const char* lobby="Flow_Setup.Act_1.LCPD.LCPD_Level.LCPD_Lobby";
    auto entered=LobbyField(base,lobby,"LCPD_LobbyEntered",0xc46b38);
    auto mainframe=LobbyField(base,lobby,"LCPD_MainframeActive",0xc46bb8);
    if(!act || !mission || !stage || !entered || !mainframe)return nullptr;
    if(*reinterpret_cast<int*>(act+16)!=1 || *reinterpret_cast<int*>(mission+16)!=1 ||
       *reinterpret_cast<int*>(stage+16)!=2)return nullptr;
    const auto active=*reinterpret_cast<unsigned char*>(mainframe+16);
    if(active>1)return nullptr;
    auto counter=reinterpret_cast<int*>(entered+16);
    // Repairing the mainframe happens during LobbyFirst, before the garage.
    if(*counter!=1 && !(*counter==2 && active==0))return nullptr;
    return counter;
}
