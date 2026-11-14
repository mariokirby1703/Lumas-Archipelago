// Intercept the real AllowDetectiveMode setter, not the CriminalScan ability.
using DetectiveSetter=void(__fastcall*)(std::uintptr_t,bool);
static DetectiveSetter detective_original=nullptr;
static volatile LONG detective_policy=0; // managed=1, entitled=2
static void __fastcall DetectiveSetterGate(std::uintptr_t actor,bool requested) {
    const LONG policy=InterlockedCompareExchange(&detective_policy,0,0);
    detective_original(actor,requested && (!(policy&1) || (policy&2)));
}
static bool InstallDetectiveGate(std::uintptr_t base) {
    if(detective_original)return true;
    const unsigned char original[]={0x40,0x57,0x48,0x83,0xec,0x50,0x48,0xc7,0x44,0x24,0x20,0xfe,0xff,0xff,0xff};
    auto entry=reinterpret_cast<unsigned char*>(base+0x649a0);
    if(std::memcmp(entry,original,sizeof(original)))return false;
    // The copied whole instructions contain no relative addresses.
    auto trampoline=reinterpret_cast<unsigned char*>(VirtualAlloc(nullptr,32,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
    if(!trampoline)return false;
    std::memcpy(trampoline,original,sizeof(original));
    const unsigned char jump[]={0xff,0x25,0,0,0,0};
    std::memcpy(trampoline+15,jump,6);
    auto resume=base+0x649af;std::memcpy(trampoline+21,&resume,8);
    DWORD previous=0;
    if(!VirtualProtect(trampoline,32,PAGE_EXECUTE_READ,&previous) ||
       !FlushInstructionCache(GetCurrentProcess(),trampoline,32)) {
        VirtualFree(trampoline,0,MEM_RELEASE);return false;
    }
    HMODULE module=nullptr;
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,
                          reinterpret_cast<LPCWSTR>(&DetectiveSetterGate),&module)) {
        VirtualFree(trampoline,0,MEM_RELEASE);return false;
    }
    if(!VirtualProtect(entry,15,PAGE_EXECUTE_READWRITE,&previous)) {
        VirtualFree(trampoline,0,MEM_RELEASE);return false;
    }
    unsigned char replacement[15]{};std::memcpy(replacement,jump,6);
    auto target=reinterpret_cast<std::uintptr_t>(&DetectiveSetterGate);
    std::memcpy(replacement+6,&target,8);replacement[14]=0x90;
    detective_original=reinterpret_cast<DetectiveSetter>(trampoline);
    std::memcpy(entry,replacement,15);
    const bool flushed=FlushInstructionCache(GetCurrentProcess(),entry,15)!=0;
    DWORD ignored=0;const bool restored=VirtualProtect(entry,15,previous,&ignored)!=0;
    return flushed && restored;
}
static DWORD ConfigureDetectiveGate(std::uintptr_t base,std::uintptr_t actor,unsigned policy) {
    if(policy>3 || policy==2)return 9;
    if(!policy && !detective_original)return 0; // Vanilla mode needs no hook.
    if(!InstallDetectiveGate(base))return 1;
    InterlockedExchange(&detective_policy,LONG(policy));
    if(policy==1) {
        // Clear the existing aura permission too; do not interrupt an active scan.
        detective_original(actor,false);
        // The original setter selects the active player's 0x5330-byte state.
        // Its event updates are native; no forced context/animation change occurs.
    }
    // Receiving the item does NOT force an aura on. Original scripts still decide
    // whether the player is near a valid detective spot; re-enter after a grant.
    return unsigned(InterlockedCompareExchange(&detective_policy,0,0))==policy ? 0 : 7;
}
static DWORD DetectiveGateCommand(std::uintptr_t base,std::uintptr_t actor,Command* c) {
    if(c->name_hash!=Hash("DETECTIVE_SCAN_POLICY") || c->model>1)return 6;
    auto result=ConfigureDetectiveGate(base,actor,c->model ? 3 : 1);
    if(!result) { c->found=1;c->owned=(InterlockedCompareExchange(&detective_policy,0,0)&2) ? 1 : 0; }
    return result;
}
