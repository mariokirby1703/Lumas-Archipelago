// Persistent, self-contained shop guards. Never point patched game code into
// this temporary DLL: the Windows hook unloads it after each request.
#include "purchase_gate_patch.h"
static bool WriteShopCode(void* target,const void* data,std::size_t count) {
    DWORD old=0,ignored=0;
    if(!VirtualProtect(target,count,PAGE_EXECUTE_READWRITE,&old))return false;
    std::memcpy(target,data,count);
    const bool flushed=FlushInstructionCache(GetCurrentProcess(),target,count)!=0;
    return VirtualProtect(target,count,old,&ignored)!=0 && flushed;
}
static bool InstallShopGuards(std::uintptr_t base,const std::uint32_t* mask) {
    const unsigned rvas[]={shop_rva_0,shop_rva_1,shop_rva_2};
    const unsigned offsets[]={shop_offset_0,shop_offset_1,shop_offset_2};
    const unsigned char* originals[]={shop_original_0,shop_original_1,shop_original_2};
    const unsigned sizes[]={sizeof(shop_original_0),sizeof(shop_original_1),sizeof(shop_original_2)};
    auto first=reinterpret_cast<unsigned char*>(base+rvas[0]);
    unsigned char* block=nullptr;
    if(first[0]==0xe9) {
        std::int32_t delta=0;std::memcpy(&delta,first+1,4);
        block=first+5+delta;
        MEMORY_BASIC_INFORMATION info{};
        if(!VirtualQuery(block,&info,sizeof(info)) || info.State!=MEM_COMMIT ||
           info.AllocationBase!=block || info.RegionSize<4096 ||
           std::memcmp(block+0x360,"LCUSHOP1",8))return false;
        // Every jump must still belong to this installation.
        for(unsigned i=0;i<3;++i) {
            auto site=reinterpret_cast<unsigned char*>(base+rvas[i]);
            std::memcpy(&delta,site+1,4);
            if(site[0]!=0xe9 || site+5+delta!=block+offsets[i])return false;
        }
        return WriteShopCode(block+0x380,mask,128);
    }
    for(unsigned i=0;i<3;++i)
        if(std::memcmp(reinterpret_cast<void*>(base+rvas[i]),originals[i],sizes[i]))return false;
    // Relative entry jumps require a free page within 2 GiB of all sites.
    const auto center=(base+rvas[0])&~std::uintptr_t(0xffff);
    for(std::uintptr_t distance=0x10000;distance<0x70000000 && !block;distance+=0x10000) {
        for(int direction=1;direction>=-1;direction-=2) {
            const auto hint=direction>0 ? center+distance : center-distance;
            block=static_cast<unsigned char*>(VirtualAlloc(reinterpret_cast<void*>(hint),4096,
                                                           MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
            if(block)break;
        }
    }
    if(!block)return false;
    const auto address=reinterpret_cast<std::uintptr_t>(block);
    std::memcpy(block+shop_offset_0,shop_code_0,sizeof(shop_code_0));RelocateShop0(block+shop_offset_0,base,address);
    std::memcpy(block+shop_offset_1,shop_code_1,sizeof(shop_code_1));RelocateShop1(block+shop_offset_1,base,address);
    std::memcpy(block+shop_offset_2,shop_code_2,sizeof(shop_code_2));RelocateShop2(block+shop_offset_2,base,address);
    std::memcpy(block+0x360,"LCUSHOP1",8);std::memcpy(block+0x380,mask,128);
    DWORD old=0;
    if(!VirtualProtect(block,4096,PAGE_EXECUTE_READ,&old) ||
       !FlushInstructionCache(GetCurrentProcess(),block,4096)) {
        VirtualFree(block,0,MEM_RELEASE);return false;
    }
    unsigned installed=0;
    for(unsigned i=0;i<3;++i) {
        unsigned char jump[16];std::memset(jump,0x90,sizeof(jump));jump[0]=0xe9;
        const auto relative=reinterpret_cast<std::intptr_t>(block+offsets[i])-
                            static_cast<std::intptr_t>(base+rvas[i]+5);
        if(relative<INT32_MIN || relative>INT32_MAX)break;
        auto delta=static_cast<std::int32_t>(relative);std::memcpy(jump+1,&delta,4);
        // Include this site in rollback even if protection restoration failed.
        installed=i+1;
        if(!WriteShopCode(reinterpret_cast<void*>(base+rvas[i]),jump,sizes[i]))break;
        if(i==2)return true;
    }
    bool restored=true;
    for(unsigned i=0;i<installed;++i)
        restored=WriteShopCode(reinterpret_cast<void*>(base+rvas[i]),originals[i],sizes[i]) && restored;
    // Leak one page if rollback failed; never free a still-referenced trampoline.
    if(restored)VirtualFree(block,0,MEM_RELEASE);
    return false;
}
// Correct the UI category count, preserving actual discovery/source banks.
static bool InstallCategoryGuard(std::uintptr_t base) {
    auto counter=reinterpret_cast<unsigned char*>(base+navigation_rva_2);
    auto label=reinterpret_cast<unsigned char*>(base+navigation_rva_3);
    if((std::memcmp(counter,navigation_original_2,sizeof(navigation_original_2)) &&
        std::memcmp(counter,navigation_replacement_2,sizeof(navigation_replacement_2))) ||
       (std::memcmp(label,navigation_original_3,sizeof(navigation_original_3)) &&
        std::memcmp(label,navigation_replacement_3,sizeof(navigation_replacement_3))))return false;
    // Remove the prior experiment: 0x26210 reads notification flags, not the
    // category selection count. Verify our allocation before restoring it.
    auto legacy=reinterpret_cast<unsigned char*>(base+shop_rva_3);
    if(std::memcmp(legacy,shop_original_3,sizeof(shop_original_3))) {
        if(legacy[0]!=0xe9)return false;
        std::int32_t delta=0;std::memcpy(&delta,legacy+1,4);
        auto block=legacy+5+delta-shop_offset_3;
        MEMORY_BASIC_INFORMATION info{};
        if(!VirtualQuery(block,&info,sizeof(info)) || info.State!=MEM_COMMIT ||
           info.AllocationBase!=block || info.RegionSize<4096 ||
           std::memcmp(block+0x300,"LCUCAT01",8))return false;
        if(!WriteShopCode(legacy,shop_original_3,sizeof(shop_original_3)))return false;
        // Retain the page: an in-flight call must never return into freed code.
    }
    if(!WriteShopCode(counter,navigation_replacement_2,sizeof(navigation_replacement_2)))return false;
    if(!WriteShopCode(label,navigation_replacement_3,sizeof(navigation_replacement_3))) {
        WriteShopCode(counter,navigation_original_2,sizeof(navigation_original_2));return false;
    }
    return true;
}
