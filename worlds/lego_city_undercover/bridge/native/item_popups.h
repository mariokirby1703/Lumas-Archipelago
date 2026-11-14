// Literal HUD messages: no localization detour, inventory mutation or save writes.
// Packed RGB used by 0x1e93d0 and consumed by renderer 0x1e83b0 at +0xc8..ca.
static std::uint32_t PopupRGB(unsigned classification) {
    // AP palette: filler #00eeee, useful #6d8be8, progression #af99ef, trap #fa8072.
    const std::uint32_t rgb[]={0x00eeee00,0x00e88b6d,0x00ef99af,0x007280fa};
    return rgb[classification];
}
struct PopupTintLease {
    std::uintptr_t base,hud,slot,text_object;
    std::uint32_t original_rgb,ap_rgb;
    float original_y,original_default_y,ap_y,ap_default_y;
    bool moved;
    UINT_PTR timer;
    ULONGLONG deadline;
    char text[288];
};
static PopupTintLease popup_tint{};
static bool PopupTintObjectCurrent() {
    const auto& t=popup_tint;
    if(!t.timer || *reinterpret_cast<std::uintptr_t*>(t.base+0x183d088)!=t.hud)return false;
    auto slots=*reinterpret_cast<std::uintptr_t*>(t.hud+0x40);
    return slots && *reinterpret_cast<std::uintptr_t*>(slots+24)==t.slot &&
        *reinterpret_cast<std::uintptr_t*>(t.slot+8)==t.text_object;
}
static void EndPopupTint() {
    __try {
        if(PopupTintObjectCurrent()) {
            auto colour=reinterpret_cast<std::uint32_t*>(popup_tint.text_object+0xc8);
            // Restore only our own RGB. Preserve native fade alpha and any newer style.
            if((*colour&0xffffff)==popup_tint.ap_rgb)
                *colour=(*colour&0xff000000)|popup_tint.original_rgb;
            if(popup_tint.moved) {
                auto y=reinterpret_cast<float*>(popup_tint.text_object+0x74);
                auto default_y=reinterpret_cast<float*>(popup_tint.text_object+0xb4);
                if(*y==popup_tint.ap_y)*y=popup_tint.original_y;
                if(*default_y==popup_tint.ap_default_y)*default_y=popup_tint.original_default_y;
                *reinterpret_cast<unsigned char*>(popup_tint.text_object+9)|=2;
            }
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) { }
    if(popup_tint.timer)KillTimer(nullptr,popup_tint.timer);
    popup_tint={};
}
static void CALLBACK PopupTintTimer(HWND,UINT,UINT_PTR id,DWORD) {
    if(id!=popup_tint.timer)return;
    bool finished=true;
    __try {
        if(PopupTintObjectCurrent()) {
            auto text=*reinterpret_cast<const char**>(popup_tint.text_object+0xe8);
            finished=GetTickCount64()>=popup_tint.deadline ||
                *reinterpret_cast<unsigned char*>(popup_tint.slot+0xb0)==7 ||
                !text || std::strncmp(text,popup_tint.text,sizeof(popup_tint.text));
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) { }
    if(finished)EndPopupTint();
}
struct ItemPopupPacket {
    std::uint32_t magic,version,pid,channel,seconds,length,classification,reserved;
    char text[288];
};
static_assert(sizeof(ItemPopupPacket)==320);
static bool PopupScreenAvailable(std::uintptr_t base,std::uintptr_t slot) {
    auto screen=*reinterpret_cast<std::uintptr_t*>(base+0x1803d98);
    return screen && *reinterpret_cast<std::uintptr_t*>(base+0x1803da0) &&
        (!*reinterpret_cast<unsigned char*>(screen+8) ||
         *reinterpret_cast<std::uintptr_t*>(slot+0xa8)==screen);
}
static DWORD ShowItemPopup(std::uintptr_t base,Command* c) {
    if(c->model || c->name_hash!=Hash("ITEM_POPUP"))return 6;
    DWORD foreground_pid=0;
    GetWindowThreadProcessId(GetForegroundWindow(),&foreground_pid);
    if(foreground_pid!=GetCurrentProcessId()) { c->found=0;return 0; }
    wchar_t name[80]{};swprintf(name,80,L"Local\\LCURewardPolicy_%lu",GetCurrentProcessId());
    HANDLE mapping=OpenFileMappingW(FILE_MAP_READ,FALSE,name);if(!mapping)return 15;
    auto view=MapViewOfFile(mapping,FILE_MAP_READ,0,0,320);
    if(!view) { CloseHandle(mapping);return 15; }
    ItemPopupPacket packet{};std::memcpy(&packet,view,320);
    UnmapViewOfFile(view);CloseHandle(mapping);
    if(packet.magic!=0x4c435550 || packet.version!=2 || packet.pid!=GetCurrentProcessId() ||
       packet.channel!=3 || packet.classification>3 ||
       packet.seconds!=(packet.classification==2 ? 6u : 3u) || !packet.length || packet.length>287 ||
       packet.text[packet.length] || packet.reserved)return 6;
    for(unsigned i=0;i<packet.length;++i) {
        unsigned char ch=packet.text[i];
        if(ch<32 || ch==127 || ch=='<' || ch=='>' || ch=='[' || ch==']' || ch=='{' || ch=='}')return 6;
    }
    const unsigned char setter[]={0x48,0x89,0x5c,0x24,0x18,0x48,0x89,0x6c,0x24,0x20};
    const unsigned char copy[]={0x48,0x85,0xc9,0x0f,0x84};
    const unsigned char tint_setter[]={0x48,0x89,0x74,0x24,0x10,0x57,0x48,0x83,0xec,0x20,0x8b,0x02};
    if(std::memcmp(reinterpret_cast<void*>(base+0x205b20),setter,sizeof(setter)) ||
       std::memcmp(reinterpret_cast<void*>(base+0x1e9580),copy,sizeof(copy)) ||
       std::memcmp(reinterpret_cast<void*>(base+0x1e93d0),tint_setter,sizeof(tint_setter)))return 1;
    auto hud=*reinterpret_cast<std::uintptr_t*>(base+0x183d088);
    if(!hud)return 4;
    auto count=*reinterpret_cast<unsigned*>(hud+0x24);
    auto slots=*reinterpret_cast<std::uintptr_t*>(hud+0x40);
    if(count<4 || count>64 || !slots)return 5;
    // State 7 is the native dormant channel observed in the pinned HUD. Refuse
    // unknown/active states. Never force removal of a native story message.
    auto message_slot=*reinterpret_cast<std::uintptr_t*>(slots+24);
    if(!message_slot || *reinterpret_cast<unsigned char*>(message_slot+0xb0)!=7) { c->found=0;return 0; }
    // Match 0x204170's native screen-ownership gate BEFORE assigning text.
    // Otherwise text can be copied while a save/modal screen rejects showing it.
    if(!PopupScreenAvailable(base,message_slot)) { c->found=0;return 0; }
    auto unlocks=*reinterpret_cast<std::uintptr_t*>(base+0x17eca98);
    if(!unlocks)return 4;
    if(*reinterpret_cast<unsigned*>(unlocks+0x218)!=*reinterpret_cast<unsigned*>(unlocks+0x21c)) {
        c->found=0;return 0;
    }
    EndPopupTint();
    // 0x205b20 takes already resolved narrow text. 0x1e9580 copies it into the
    // game's allocation; no pointers into this temporary DLL/mapping survive.
    using SetText=void(__fastcall*)(std::uintptr_t,unsigned,const char*,unsigned char,float);
    reinterpret_cast<SetText>(base+0x205b20)(hud,packet.channel,packet.text,2,float(packet.seconds));
    auto slot=*reinterpret_cast<std::uintptr_t*>(slots+packet.channel*8);
    auto text_object=*reinterpret_cast<std::uintptr_t*>(slot+8);
    if(!text_object)return 7;
    auto copied=*reinterpret_cast<const char**>(text_object+0xe8);
    if(!copied || std::strncmp(copied,packet.text,packet.length+1))return 7;
    // A copied string alone does not mean the native show request succeeded.
    if(*reinterpret_cast<unsigned char*>(slot+0xb0)==7) { c->found=0;return 0; }
    // Keep the timer callback valid after the temporary RPC hook is removed.
    // The versioned DLL is pinned for this game process only, never written to disk.
    HMODULE module=nullptr;
    if(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,
                         reinterpret_cast<LPCWSTR>(&PopupTintTimer),&module)) {
        auto timer=SetTimer(nullptr,0,50,PopupTintTimer);
        if(timer) {
            auto colour=*reinterpret_cast<std::uint32_t*>(text_object+0xc8);
            auto rgb=PopupRGB(packet.classification);
            popup_tint.base=base;popup_tint.hud=hud;popup_tint.slot=slot;popup_tint.text_object=text_object;
            popup_tint.original_rgb=colour&0xffffff;popup_tint.ap_rgb=rgb;popup_tint.timer=timer;
            auto y=reinterpret_cast<float*>(text_object+0x74);
            auto default_y=reinterpret_cast<float*>(text_object+0xb4);
            // Native GUI coordinates are 1280x720. Shift the normal centre band
            // 280 logical units down, leaving room for subtitles and the edge.
            if(std::isfinite(*y) && std::isfinite(*default_y) &&
               *y>=-720 && *y<=720 && *default_y>=-720 && *default_y<=720) {
                popup_tint.original_y=*y;popup_tint.original_default_y=*default_y;
                popup_tint.ap_y=*y+280;popup_tint.ap_default_y=*default_y+280;
                popup_tint.moved=true;*y=popup_tint.ap_y;*default_y=popup_tint.ap_default_y;
                *reinterpret_cast<unsigned char*>(text_object+9)|=2;
            }
            popup_tint.deadline=GetTickCount64()+packet.seconds*1000+500;
            std::memcpy(popup_tint.text,packet.text,sizeof(packet.text));
            auto tinted=(colour&0xff000000)|rgb;
            using SetTint=void(__fastcall*)(std::uintptr_t,const std::uint32_t*,bool);
            reinterpret_cast<SetTint>(base+0x1e93d0)(text_object,&tinted,false);
            c->owned=1; // Tint installed; this is not item ownership.
        }
    }
    c->found=1;return 0;
}
