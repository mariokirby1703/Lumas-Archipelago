// Scoped experimental city-boundary rollback using the game's teleport routines.
// No caller coordinates, no save/story/inventory edits, no forced actor context.
struct AreaPose { alignas(16) float matrix[16]; };
struct AreaCheckpoint {
    std::uintptr_t profile=0,world=0,actor=0,ride=0,ride_control=0;
    std::uintptr_t ride_model=0;
    unsigned ride_kind=0;
    std::uint32_t binding[4]{},district=0;
    AreaPose pose{};bool valid=false;
};
static AreaCheckpoint area_checkpoint;
static AreaCheckpoint area_foot_checkpoint;
static bool area_disembark_pending=false;
static AreaCheckpoint area_history[16];
static unsigned area_history_cursor=0;
static bool AreaSameIdentity(const AreaCheckpoint& a,const AreaCheckpoint& b) {
    return a.profile==b.profile && a.world==b.world && a.actor==b.actor && a.ride==b.ride &&
           a.ride_control==b.ride_control && a.ride_model==b.ride_model && a.ride_kind==b.ride_kind && a.district==b.district &&
           !std::memcmp(a.binding,b.binding,16);
}
static void AreaReplyPose(Command* c,const AreaCheckpoint& point) {
    c->receipt=point.ride_kind;
    std::memcpy(c->binding,point.pose.matrix+12,12); // reply only, after all binding validation
}
static std::uintptr_t AreaPointer(std::uintptr_t p) { return *reinterpret_cast<std::uintptr_t*>(p); }
static bool AreaCityActor(std::uintptr_t base,std::uintptr_t actor) {
    auto registry=AreaPointer(base+0x1c402d8);auto index=*reinterpret_cast<unsigned short*>(actor+0x28);
    if(!registry || index>0x7ff)return false;
    auto entry=AreaPointer(registry+0x18+index*8);if(!entry)return false;
    auto owner=AreaPointer(entry+0xd8);if(!owner)return false;
    auto tile=AreaPointer(owner+0xb18);if(!tile)return false;
    auto text=reinterpret_cast<const char*>(AreaPointer(tile+0x68));if(!text || !std::memchr(text,0,96))return false;
    if(Hash(text)==Hash("Lego_City"))return true;
    // Scene owners in streamed city tiles use these prefixes. Explicitly reject
    // standalone interiors even when a background city grid is still resident.
    const char* last=std::strrchr(text,'_');if(!last || std::strlen(last+1)!=4)return false;
    for(unsigned i=0;i<4;++i)if(last[1+i]<'0' || last[1+i]>'9')return false;
    char a=text[0],b=text[1];if(a>='a' && a<='z')a-=32;if(b>='a' && b<='z')b-=32;
    return text[2]=='_' && ((a=='S' && b=='F') || (a=='W' && b=='I') || (a=='N' && b=='Y') ||
        (a=='I' && b=='S') || (a=='B' && b=='R'));
}
static bool AreaFinite(const AreaPose& pose) {
    for(float value:pose.matrix)if(!std::isfinite(value) || std::fabs(value)>100000)return false;
    return std::fabs(pose.matrix[15]-1.f)<0.001f;
}
static std::uint32_t AreaDistrict(std::uintptr_t base,const float* pos) {
    auto world=AreaPointer(base+0x1c6a768);if(!world)return 0;
    auto scene=AreaPointer(world+0x178);if(!scene)return 0;
    auto entity=AreaPointer(scene+0x98);if(!entity || AreaPointer(AreaPointer(entity))!=base+0x3be70)return 0;
    int index=*reinterpret_cast<int*>(base+0x17ebc30);if(index<0 || index>=128)return 0;
    auto grid=AreaPointer(entity+0xd0+index*8);if(!grid)return 0;
    auto nested=AreaPointer(grid+0x38);if(nested)grid=nested;
    auto origin=reinterpret_cast<const float*>(grid+0x100);
    float size=*reinterpret_cast<float*>(grid+0x110),factor=*reinterpret_cast<float*>(base+0xc0fe1c);
    int width=*reinterpret_cast<int*>(base+0x1165910),height=*reinterpret_cast<int*>(base+0x1165914);
    if(!std::isfinite(size) || size<=0 || !std::isfinite(factor) || width<=0 || height<=0 || width>256 || height>256)return 0;
    float fx=(pos[0]-origin[0])*(1.f/size),fz=((pos[2]-origin[2])*factor)*(1.f/size);
    if(!std::isfinite(fx) || !std::isfinite(fz) || fx<0 || fz<0 || fx>=width || fz>=height)return 0;
    auto table=AreaPointer(grid+0xf0);if(!table)return 0;
    auto cell=AreaPointer(table+(int(fz)*width+int(fx))*8);if(!cell)return 0;
    auto tile=AreaPointer(cell+0x58);if(!tile)return 0;
    auto text=reinterpret_cast<const char*>(AreaPointer(tile+0x68));if(!text || !std::memchr(text,0,96))return 0;
    const char* districts[]={"SF_Docks","SF_Residential","WI_Forest","WI_Farmlands","BR_Brooklyn_Bridge","BR_Golden_Gate","BR_Twin_Bridge",
        "IS_Liberty_Island","IS_Prison_Island","IS_Space_Centre","NY_Airport","NY_Beach","NY_Canal","NY_Central_Park","NY_Chinatown",
        "NY_Downtown","NY_Downtown_East","NY_Downtown_West","NY_Little_Italy","NY_Times_Square","NY_Tunnel","NY_Uptown"};
    // Match the entire prefix before the final numeric tile suffix. Never match
    // NY_Downtown_East as NY_Downtown and never infer from a nearby collectible.
    auto last=std::strrchr(text,'_');if(!last || std::strlen(last+1)!=4)return 0;
    for(unsigned i=0;i<4;++i)if(last[1+i]<'0' || last[1+i]>'9')return 0;
    char prefix[96]{};std::memcpy(prefix,text,std::size_t(last-text));
    for(auto district:districts)if(Hash(prefix)==Hash(district))return Hash(district);
    if(Hash(prefix)==Hash("NY_Monaco_Tunnel"))return Hash("NY_Tunnel");
    return 0;
}
static std::uintptr_t AreaRidden(std::uintptr_t base,std::uintptr_t actor) {
    // Character_GetRidden (112ba0): brain+88 virtual 240 -> base interface target.
    // Only the reviewed MechCharacterBaseInterface getter 1f8830 is accepted.
    auto component=AreaPointer(actor+0x340);if(!component)return 0;
    auto controller=AreaPointer(component+0x88);if(!controller)return 0;
    auto getter=AreaPointer(AreaPointer(controller)+0x240);
    const unsigned char prefix[]={0x48,0x8b,0x41,0x20,0xc3};
    if(getter!=base+0x1f8830 || std::memcmp(reinterpret_cast<void*>(getter),prefix,sizeof(prefix)))return 0;
    return AreaPointer(controller+0x20);
}
static bool AreaCurrentPose(std::uintptr_t base,std::uintptr_t actor,int context,AreaPose& pose,std::uintptr_t& ride,std::uintptr_t& control,DWORD& failure,unsigned& kind) {
    failure=3;
    ride=0;control=0;kind=0;
    auto weak_vehicle=AreaPointer(actor+0x428),vehicle_counter=AreaPointer(actor+0x430);
    if(!weak_vehicle || (vehicle_counter && *reinterpret_cast<int*>(vehicle_counter+4)<=0)) {
        auto creature=AreaRidden(base,actor);
        if(creature && creature!=actor && (context==46 || context==152 || context==124 || context==157)) {
            if(!AreaCityActor(base,creature) || AreaPointer(AreaPointer(creature+0x10)+0xf0)!=base+0x49ecf0) {failure=5;return false;}
            ride=creature;kind=2;control=AreaPointer(AreaPointer(actor+0x340)+0x88);
            std::memcpy(pose.matrix,reinterpret_cast<void*>(creature+0x1c0),64);
            if(!AreaFinite(pose)) {failure=5;return false;}return true;
        }
    }
    if(context==46) {
        auto weak=AreaPointer(actor+0x428),counter=AreaPointer(actor+0x430);
        if(weak && (!counter || *reinterpret_cast<int*>(counter+4)>0))return false; // never detach a mounted character
        if(AreaPointer(AreaPointer(actor+0x10)+0xf0)!=base+0x49ecf0) {failure=5;return false;}
        // Translation is actor+0x1f0; retain orientation from the accessor matrix.
        std::memcpy(pose.matrix,reinterpret_cast<void*>(actor+0x1c0),64);
    } else if(context==157 || context==11) {
        auto weak=AreaPointer(actor+0x428);control=AreaPointer(actor+0x430);
        if(!weak || !control || *reinterpret_cast<int*>(control+4)<=0)return false;
        ride=AreaPointer(weak);if(!ride)return false;
        kind=1;
        auto getter=AreaPointer(AreaPointer(ride)+0xf0);
        if(getter==base+0x506fe0) {
            std::memcpy(pose.matrix,reinterpret_cast<void*>(ride+0x50),64);
        } else if(getter==base+0x4a9370) {
            // Reviewed getter: vehicle+348 owns physics transform at +60.
            const unsigned char prefix[]={0x4c,0x8b,0x81,0x48,0x03,0,0};
            if(std::memcmp(reinterpret_cast<void*>(getter),prefix,sizeof(prefix))) {failure=1;return false;}
            auto physics=AreaPointer(ride+0x348);
            if(!physics) {failure=3;return false;}
            std::memcpy(pose.matrix,reinterpret_cast<void*>(physics+0x60),64);
        } else {failure=5;return false;}
    } else return false;
    if(!AreaFinite(pose)) {failure=5;return false;}return true;
}
static DWORD AreaReturnCommand(std::uintptr_t base,std::uintptr_t actor,int context,Command* c) {
    if(c->name_hash!=Hash(c->opcode==21 ? "AREA_CHECKPOINT" : c->opcode==23 ? "AREA_DISEMBARK" : "AREA_RETURN"))return 6;
    if(!(c->binding[0]|c->binding[1]|c->binding[2]|c->binding[3]))return 6;
    if(!AreaCityActor(base,actor))return 20;
    auto profile=AreaPointer(base+0x1c7f160),world=AreaPointer(base+0x1c6a768),bank=AreaPointer(base+0x1c7cbb8);
    if(!profile || !world || !bank || bank!=profile+0x122e0)return 4;
    auto marker=reinterpret_cast<unsigned char*>(bank+0x80+1002);
    bool empty=true;for(unsigned i=0;i<22;++i)empty=empty && marker[i]==0;
    // First progression receipts need not include currency, so a backed-up,
    // host-bound fresh slot can still have an empty native currency marker.
    // Do not manufacture that persisted marker just to capture a position.
    if(!empty && (marker[0]!='A' || marker[1]!='P' || std::memcmp(marker+2,c->binding,16)))return 13;
    AreaPose current{};std::uintptr_t ride=0,control=0;
    DWORD pose_failure=3;unsigned ride_kind=0;
    if(!AreaCurrentPose(base,actor,context,current,ride,control,pose_failure,ride_kind))return pose_failure;
    auto district=AreaDistrict(base,current.matrix+12);
    if(!district || district!=c->model)return 20;
    if(c->opcode==23) {
        if(ride_kind==2)return 3; // creatures keep their rider relationship
        AreaCheckpoint saved=area_foot_checkpoint;
        if(!saved.valid || saved.profile!=profile || saved.world!=world || saved.actor!=actor ||
           std::memcmp(saved.binding,c->binding,16))return 21;
        for(unsigned age=16;age>1;--age) {
            const auto& candidate=area_history[(area_history_cursor+16-age)%16];
            if(!candidate.valid || !AreaSameIdentity(candidate,saved))continue;
            float d=0;for(unsigned i=12;i<15;++i) {float v=current.matrix[i]-candidate.pose.matrix[i];d+=v*v;}
            if(d<=90.f*90.f && AreaDistrict(base,candidate.pose.matrix+12)==candidate.district) {saved=candidate;break;}
        }
        if(AreaDistrict(base,saved.pose.matrix+12)!=saved.district || saved.district==district)return 20;
        float distance=0;for(unsigned i=12;i<15;++i) {float d=current.matrix[i]-saved.pose.matrix[i];distance+=d*d;}
        if(distance>90.f*90.f)return 22;
        const unsigned char teleport[]={0x45,0x33,0xc0,0xe9,0x08,0x02,0,0};
        const unsigned char clear[]={0x48,0x83,0xec,0x58};
        if(std::memcmp(reinterpret_cast<void*>(base+0x6709f0),teleport,sizeof(teleport)) ||
           std::memcmp(reinterpret_cast<void*>(base+0x1105d0),clear,sizeof(clear)))return 1;
        if(ride) {
            if(!area_disembark_pending) {
                if(!AreaPointer(actor+0x340))return 3;
                // Exact Character_ClearVehicle script body; uses only the character argument.
                using Clear=unsigned(__fastcall*)(void*,std::uintptr_t,void*);
                reinterpret_cast<Clear>(base+0x1105d0)(nullptr,actor+0x10,nullptr);
                area_disembark_pending=true;
            }
            c->owned=1;c->found=0;return 0; // wait for a fresh unmounted observation
        }
        if(context!=46)return 3;
        using Teleport=unsigned(__fastcall*)(std::uintptr_t,const float*);
        if(reinterpret_cast<Teleport>(base+0x6709f0)(actor,saved.pose.matrix+12))return 3;
        area_disembark_pending=false;AreaReplyPose(c,saved);c->owned=1;c->found=1;return 0;
    }
    if(c->opcode==21) {
        HMODULE module=nullptr;
        if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,
            reinterpret_cast<LPCWSTR>(&AreaReturnCommand),&module))return 5;
        if(c->receipt==0xffffffffu) {
            for(auto& point:area_history)point={};area_history_cursor=0;
            area_foot_checkpoint={};area_disembark_pending=false;
        }
        area_checkpoint={};area_checkpoint.profile=profile;area_checkpoint.world=world;area_checkpoint.actor=actor;
        area_checkpoint.ride=ride;area_checkpoint.ride_control=control;area_checkpoint.district=district;
        area_checkpoint.ride_kind=ride_kind;
        area_checkpoint.ride_model=ride_kind==2 ? AreaPointer(ride+0x650) : 0;
        area_checkpoint.pose=current;std::memcpy(area_checkpoint.binding,c->binding,16);area_checkpoint.valid=true;
        area_history[area_history_cursor++%16]=area_checkpoint;
        if(!ride && context==46) {area_foot_checkpoint=area_checkpoint;area_disembark_pending=false;}
        AreaReplyPose(c,area_checkpoint);c->found=district;c->owned=1;return 0;
    }
    AreaCheckpoint saved=area_checkpoint;
    if(!saved.valid || saved.profile!=profile || saved.world!=world || saved.actor!=actor || saved.ride!=ride ||
       saved.ride_control!=control || saved.ride_kind!=ride_kind ||
       (ride_kind==2 && saved.ride_model!=AreaPointer(ride+0x650)) || std::memcmp(saved.binding,c->binding,16))return 21;
    // Prefer an older, actually captured pose of the SAME allowed district and
    // SAME actor/ride. No synthetic ground coordinate and no cross-world reuse.
    // Every candidate is still subject to the existing distance/tile guards.
    for(unsigned age=16;age>1;--age) {
        const auto& candidate=area_history[(area_history_cursor+16-age)%16];
        if(!candidate.valid || !AreaSameIdentity(candidate,saved))continue;
        float d=0;for(unsigned i=12;i<15;++i) {float v=current.matrix[i]-candidate.pose.matrix[i];d+=v*v;}
        if(d<=90.f*90.f && AreaDistrict(base,candidate.pose.matrix+12)==candidate.district) {saved=candidate;break;}
    }
    if(AreaDistrict(base,saved.pose.matrix+12)!=saved.district)return 20;
    float distance=0;
    for(unsigned i=12;i<15;++i) {float delta=current.matrix[i]-saved.pose.matrix[i];distance+=delta*delta;}
    // A nearby boundary rollback is reviewed here, not cross-map fast travel.
    if(distance>90.f*90.f || saved.district==district)return 22;
    if(ride && ride_kind==1) {
        const unsigned char prefix[]={0x48,0x89,0x5c,0x24,8,0x48,0x89,0x74,0x24,0x10,0x57,0x48,0x83,0xec,0x20};
        if(std::memcmp(reinterpret_cast<void*>(base+0x4abe70),prefix,sizeof(prefix)))return 1;
        using Fn=void(__fastcall*)(std::uintptr_t,const AreaPose*);
        reinterpret_cast<Fn>(base+0x4abe70)(ride,&saved.pose);
    } else {
        const unsigned char prefix[]={0x45,0x33,0xc0,0xe9,0x08,0x02,0,0};
        // Encoding is taken from the supported EXE; unknown code is refused.
        if(std::memcmp(reinterpret_cast<void*>(base+0x6709f0),prefix,sizeof(prefix)))return 1;
        using Fn=unsigned(__fastcall*)(std::uintptr_t,const float*);
        if(reinterpret_cast<Fn>(base+0x6709f0)(ride_kind==2 ? ride : actor,saved.pose.matrix+12))return 3;
    }
    AreaReplyPose(c,saved);c->found=saved.district;c->owned=1;return 0;
}
