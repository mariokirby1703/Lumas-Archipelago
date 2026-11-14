struct CurrencyRecord { std::uint32_t index,kind,amount; };
struct CurrencyBatch {
    std::uint32_t magic,version,pid,count,binding[4];
    CurrencyRecord records[24];
};
static_assert(sizeof(CurrencyBatch)==320);
static DWORD CreditBatch(std::uintptr_t base,Command* c) {
    if(c->model || Hash("CURRENCY_BATCH")!=c->name_hash)return 6;
    wchar_t name[80]{};swprintf(name,80,L"Local\\LCURewardPolicy_%lu",GetCurrentProcessId());
    HANDLE mapping=OpenFileMappingW(FILE_MAP_READ,FALSE,name);if(!mapping)return 15;
    auto view=MapViewOfFile(mapping,FILE_MAP_READ,0,0,320);
    if(!view) { CloseHandle(mapping);return 15; }
    CurrencyBatch batch{};std::memcpy(&batch,view,320);UnmapViewOfFile(view);CloseHandle(mapping);
    if(batch.magic!=0x4c435542 || batch.version!=1 || batch.pid!=GetCurrentProcessId() ||
       !batch.count || batch.count>24 || std::memcmp(batch.binding,c->binding,16))return 6;
    auto profile=*reinterpret_cast<std::uintptr_t*>(base+0x1c7f160);
    auto bank=*reinterpret_cast<std::uintptr_t*>(base+0x1c7cbb8);
    auto stats=*reinterpret_cast<std::uintptr_t*>(base+0x1c7a830);
    auto models=*reinterpret_cast<std::uintptr_t*>(base+0x17ebd38);
    if(!profile || !bank || !stats || !models)return 4;
    if(bank!=profile+0x122e0 || *reinterpret_cast<std::uint32_t*>(models+0xe0)!=1002)return 5;
    auto marker=reinterpret_cast<unsigned char*>(bank+0x80+1002);
    bool empty=true;for(unsigned i=0;i<22;++i)empty=empty && marker[i]==0;
    std::uint32_t next=0;
    if(!empty) {
        if(marker[0]!='A' || marker[1]!='P' || std::memcmp(marker+2,c->binding,16))return 13;
        std::memcpy(&next,marker+18,4);
    }
    std::uint64_t studs=0;std::uint32_t bricks=0,credited=0,last=0;
    for(unsigned i=0;i<batch.count;++i) {
        const auto& r=batch.records[i];
        if(r.index==UINT32_MAX || (i && r.index<=last))return 9;
        last=r.index;
        if(r.kind==6) { if(r.amount!=1000 && r.amount!=10000 && r.amount!=100000)return 9; }
        else if(r.kind==7) { if(r.amount!=100 && r.amount!=250 && r.amount!=1000 && r.amount!=10000)return 9; }
        else return 9;
        if(r.index<next)continue;
        if(r.kind==6)studs+=r.amount;else bricks+=r.amount;
        ++credited;
    }
    if(!credited) { c->found=0;c->owned=1;return 0; }
    auto controller=stats+0x3638;
    if(!*reinterpret_cast<unsigned char*>(controller+0x21))return 11;
    if(*reinterpret_cast<unsigned char*>(controller+0x23) || *reinterpret_cast<unsigned char*>(controller+0x20))return 14;
    const unsigned char getter[]={0x80,0xb9,0x5d,0x33,0,0,0};
    const unsigned char saver[]={0x80,0x79,0x21,0};
    if(std::memcmp(reinterpret_cast<void*>(base+0x3bf70),getter,sizeof(getter)) ||
       std::memcmp(reinterpret_cast<void*>(base+0x40e30),getter,sizeof(getter)) ||
       std::memcmp(reinterpret_cast<void*>(base+0xd18b0),saver,sizeof(saver)))return 1;
    using Get=std::uint32_t(*)(void*);using Set=void(*)(void*,std::uint32_t);using Save=void(*)(void*);
    auto get=reinterpret_cast<Get>(base+0x3bf70);auto set=reinterpret_cast<Set>(base+0x40e30);
    auto wallet=reinterpret_cast<std::uint64_t*>(profile+0xfb10);
    const auto old_wallet=*wallet;const auto old_bricks=get(reinterpret_cast<void*>(stats));
    if(old_wallet>UINT64_MAX-studs || old_bricks>INT32_MAX-bricks)return 12;
    if(bricks)set(reinterpret_cast<void*>(stats),old_bricks+bricks);
    *wallet=old_wallet+studs;
    if(*wallet!=old_wallet+studs || get(reinterpret_cast<void*>(stats))!=old_bricks+bricks)return 7;
    marker[0]='A';marker[1]='P';std::memcpy(marker+2,c->binding,16);
    next=last+1;std::memcpy(marker+18,&next,4);
    reinterpret_cast<Save>(base+0xd18b0)(reinterpret_cast<void*>(controller));
    c->found=credited;c->owned=1;return 0;
}
