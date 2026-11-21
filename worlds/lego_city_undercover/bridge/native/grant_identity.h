// Packet found/owned carry an optional expected profile address on entry.
// Validate it on the game thread before any mutation; reply fields are cleared.
static DWORD ValidateGrantIdentity(std::uintptr_t base,Command* c) {
    const auto expected=std::uintptr_t(c->found)|(std::uintptr_t(c->owned)<<32);
    if(!expected)return 0; // Legacy local test commands keep their existing API.
    if(!(c->binding[0]|c->binding[1]|c->binding[2]|c->binding[3]))return 6;
    const auto profile=*reinterpret_cast<std::uintptr_t*>(base+0x1c7f160);
    const auto bank=*reinterpret_cast<std::uintptr_t*>(base+0x1c7cbb8);
    if(!profile || profile!=expected || bank!=profile+0x122e0)return 13;
    const auto marker=reinterpret_cast<const unsigned char*>(bank+0x80+1002);
    bool empty=true;for(unsigned i=0;i<22;++i)empty=empty && marker[i]==0;
    if(!empty && (marker[0]!='A' || marker[1]!='P' || std::memcmp(marker+2,c->binding,16)))return 13;
    c->found=0;c->owned=0;return 0;
}
