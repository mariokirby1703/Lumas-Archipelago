// Pinned Win64 immediate-mode menu callbacks, NOT PauseMenuDrawer/BAML nodes.
// 54f700 copies GAME menu records after five engine records. The live pause
// record is index 7 (ID 2); source record index 2 is not the runtime index.
#include "pause_menu_logic.h"
namespace lcu_pause {
using Callback=void(__fastcall*)(unsigned char*);
using DrawRow=void(__fastcall*)(unsigned char*,const char*);
using DrawDimRow=void(__fastcall*)(unsigned char*,const char*,unsigned char);
using PushMenu=void*(__fastcall*)(int,int,int);
using PopMenu=void(__fastcall*)();

struct Record {
    int id,padding;
    Callback init,draw,input,close;
    short saved_column,saved_row;
    unsigned char flags[4];
};
static_assert(sizeof(Record)==0x30);
static State state;
static std::uintptr_t image=0;
static int registered_index=-1;
static Callback original_draw=nullptr,original_input=nullptr;
static DrawRow draw_row=nullptr;
static DrawDimRow draw_dim_row=nullptr;
static PushMenu push_menu=nullptr;
static PopMenu pop_menu=nullptr;
static const char* resume_text=nullptr;
static const float* default_row_spacing=nullptr;
static const float* native_row_scale=nullptr;

template<class T> static T& field(unsigned char* context,unsigned offset) {
    return *reinterpret_cast<T*>(context+offset);
}
static bool valid_context(unsigned char* context,int record) {
    const auto address=reinterpret_cast<std::uintptr_t>(context);
    const auto first=image+0x1c4c9f0;
    return address>=first && address<first+10*0xf0 &&
        (address-first)%0xf0==0 && field<short>(context,0x14)==record;
}
static void __fastcall RootDraw(unsigned char* context) {
    if(!state.enabled || !valid_context(context,7) || field<short>(context,0xe)!=0) {
        original_draw(context);return;
    }
    // Insert after Resume without hooking the global text renderer. The vanilla
    // callback still generates every optional row exactly once. Its Resume is
    // clipped; all remaining native rows retain their positions shifted by one.
    // Draw Resume and Chapter Select into the two reserved positions afterwards.
    // Measurement mode uses the same native counter path and suppresses drawing.
    const float start_y=field<float>(context,0xa4);
    const float configured_spacing=field<float>(context,0xe4);
    const float spacing=(configured_spacing ? configured_spacing : *default_row_spacing)*(*native_row_scale);
    const bool insert=field<std::uintptr_t>(context,0xd0)==0;
    if(insert) {
        field<int>(context,0x98)=1;
        field<short>(context,0xe)=2;
        field<short>(context,0x12)=24;
        field<float>(context,0xa4)=start_y+spacing;
    }
    original_draw(context);
    const int row=field<int>(context,0x98);
    state.vanilla_rows=row-(insert ? 1 : 0);
    state.root_row=insert ? 1 : row;
    ++state.root_draws;
    field<short>(context,0xe)=0;
    field<short>(context,0x12)=static_cast<short>(state.vanilla_rows);
    if(insert) {
        const float end_y=field<float>(context,0xa4);
        field<int>(context,0x98)=0;
        field<float>(context,0xa4)=start_y;
        draw_row(context,resume_text);
        draw_row(context,"Chapter Select");
        field<int>(context,0x98)=row;
        field<float>(context,0xa4)=end_y;
    } else {
        draw_row(context,"Chapter Select");
    }
}
static void __fastcall RootInput(unsigned char* context) {
    if(state.enabled && valid_context(context,7) && state.root_row>=1) {
        const int selected=field<int>(context,0x40);
        if(selected==state.root_row && field<int>(context,0x70)) {
            push_menu(chapter_menu_id,0,-1);return;
        }
        // Visible entries below the inserted row still invoke their original
        // vanilla actions (station return, Options, Extras, quit, etc.).
        if(selected>state.root_row)field<int>(context,0x40)=selected-1;
        original_input(context);
        if(valid_context(context,7))field<int>(context,0x40)=selected;
        return;
    }
    original_input(context);
}
static void __fastcall ChaptersDraw(unsigned char* context) {
    if(!valid_context(context,registered_index))return;
    static const char* const labels[]={
        "Chapter 1", "Chapter 2", "Chapter 3", "Chapter 4", "Chapter 5",
        "Chapter 6", "Chapter 7", "Chapter 8", "Chapter 9", "Chapter 10",
        "Chapter 11", "Chapter 12", "Chapter 13", "Chapter 14", "Chapter 15"};
    // Chapter transactions are not yet bound. Grey entries must never launch
    // assignments, set completion flags or masquerade as functional starts.
    auto dim=draw_dim_row;
    // Match the original Extras scrolling layout: normal-sized text, selected
    // row centered, and the rest faded near the HUD/statistics. The engine
    // handles arrows, controller, repeat timing and full-list selection bounds.
    int selected=field<short>(context,0xa);
    if(selected<0 || selected>=rows)selected=0;
    field<float>(context,0xe0)=0.50f;
    field<float>(context,0xe4)=row_spacing;
    field<short>(context,0x12)=rows-1;
    for(int i=0;i<rows;++i) {
        field<float>(context,0xa4)=row_position(i,selected);
        dim(context,labels[i],row_alpha(i,selected,48));
    }
    ++state.chapter_draws;
}
static void __fastcall ChaptersInput(unsigned char* context) {
    if(!valid_context(context,registered_index))return;
    const auto selected=field<int>(context,0x40);
    switch(action(selected,field<int>(context,0x70)!=0,field<int>(context,0x74)!=0)) {
    case Action::Back:
        pop_menu();
        return;
    default: break;
    }
}
static bool signatures(std::uintptr_t base) {
    const unsigned char draw[]={0x48,0x89,0x5c,0x24,0x10,0x48,0x89,0x6c,0x24,0x18};
    const unsigned char input[]={0x40,0x56,0x57,0x48,0x83,0xec,0x38,0x80};
    const unsigned char row[]={0x48,0x8b,0x05,0x51,0xa7,0x3b,0x01};
    const unsigned char dim[]={0x48,0x8b,0xc4,0x48,0x89,0x58,0x08};
    const unsigned char push[]={0x48,0x89,0x5c,0x24,0x08,0x48,0x89,0x6c,0x24,0x10};
    const unsigned char pop[]={0x48,0x83,0xec,0x28,0x48,0x63,0x15};
    return !std::memcmp(reinterpret_cast<void*>(base+0x80b090),draw,sizeof(draw)) &&
        !std::memcmp(reinterpret_cast<void*>(base+0x80ab60),input,sizeof(input)) &&
        !std::memcmp(reinterpret_cast<void*>(base+0x8af760),row,sizeof(row)) &&
        !std::memcmp(reinterpret_cast<void*>(base+0x54f310),dim,sizeof(dim)) &&
        !std::memcmp(reinterpret_cast<void*>(base+0x550140),push,sizeof(push)) &&
        !std::memcmp(reinterpret_cast<void*>(base+0x54eca0),pop,sizeof(pop));
}
static DWORD Configure(std::uintptr_t base,Command* command) {
    if(command->name_hash!=Hash("PAUSE_CHAPTER_MENU") || command->model>3)return 6;
    if(!signatures(base))return 1;
    auto table=reinterpret_cast<Record*>(base+0x115d7c0);
    auto count=reinterpret_cast<int*>(base+0x115efe0);
    if(table[7].id!=2 || *count<47 || *count>123)return 5;
    if(command->model==3) {
        // Explicit development handoff: the host has disabled and hash-verified
        // the prior bridge. All four callbacks must belong to that same module,
        // and the exact expected root pointers travel in the command packet.
        if(registered_index>=0 || command->receipt!=47 || *count!=48 ||
           table[47].id!=chapter_menu_id)return 5;
        std::uintptr_t expected[2]{};std::memcpy(expected,command->binding,16);
        if(reinterpret_cast<std::uintptr_t>(table[7].draw)!=expected[0] ||
           reinterpret_cast<std::uintptr_t>(table[7].input)!=expected[1])return 5;
        HMODULE owner=nullptr;
        const Callback callbacks[]={table[7].draw,table[7].input,table[47].draw,table[47].input};
        for(auto callback : callbacks) {
            HMODULE current=nullptr;
            if(!callback || !GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                reinterpret_cast<LPCWSTR>(callback),&current) ||
                current==reinterpret_cast<HMODULE>(base) || (owner && current!=owner))return 5;
            owner=current;
        }
        const int top=*reinterpret_cast<int*>(base+0x115efc4);
        if(top<0 || top>=10)return 3;
        auto active=reinterpret_cast<unsigned char*>(base+0x1c4c9f0+top*0xf0);
        if(field<short>(active,0x14)!=7)return 3;
        for(int i=0;i<10;++i)if(field<short>(reinterpret_cast<unsigned char*>(base+0x1c4c9f0+i*0xf0),0x14)==47)return 3;
        InterlockedExchangePointer(reinterpret_cast<void* volatile*>(&table[7].draw),reinterpret_cast<void*>(base+0x80b090));
        InterlockedExchangePointer(reinterpret_cast<void* volatile*>(&table[7].input),reinterpret_cast<void*>(base+0x80ab60));
        table[47]={};InterlockedDecrement(reinterpret_cast<volatile LONG*>(count));
        command->model=1;
    }
    if(registered_index>=0) {
        if(image!=base || table[7].draw!=RootDraw || table[7].input!=RootInput ||
           table[registered_index].draw!=ChaptersDraw || table[registered_index].input!=ChaptersInput)return 5;
    } else {
        if(table[7].draw!=reinterpret_cast<Callback>(base+0x80b090) ||
           table[7].input!=reinterpret_cast<Callback>(base+0x80ab60))return 5;
        for(int i=0;i<*count;++i)if(table[i].id==chapter_menu_id)return 5;
    }
    if(command->model==1 && registered_index<0) {
        // Publish only complete records/callbacks on the game's window thread.
        // This is a writable engine dispatch table, not executable code.
        MEMORY_BASIC_INFORMATION memory{};
        if(!VirtualQuery(&table[*count],&memory,sizeof(memory)) ||
           memory.State!=MEM_COMMIT || (memory.Protect&0xff)!=PAGE_READWRITE)return 5;
        HMODULE module=nullptr;
        if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,
              reinterpret_cast<LPCWSTR>(&RootDraw),&module))return 1;
        image=base;
        auto language=reinterpret_cast<std::uintptr_t*>(base+0x1190cd8);
        if(!language[1] || *reinterpret_cast<int*>(base+0x1190cd8+0x18)<=0x21)return 5;
        resume_text=reinterpret_cast<const char**>(language[1])[0x21];
        if(!resume_text)return 5;
        default_row_spacing=reinterpret_cast<const float*>(base+0x115d7bc);
        native_row_scale=reinterpret_cast<const float*>(base+0x115efcc);
        draw_row=reinterpret_cast<DrawRow>(base+0x8af760);
        draw_dim_row=reinterpret_cast<DrawDimRow>(base+0x54f310);
        push_menu=reinterpret_cast<PushMenu>(base+0x550140);
        pop_menu=reinterpret_cast<PopMenu>(base+0x54eca0);
        original_draw=table[7].draw;original_input=table[7].input;
        registered_index=*count;
        Record record{};record.id=chapter_menu_id;record.draw=ChaptersDraw;record.input=ChaptersInput;
        record.saved_column=-1;record.saved_row=-1;
        table[registered_index]=record;
        InterlockedIncrement(reinterpret_cast<volatile LONG*>(count));
        InterlockedExchangePointer(reinterpret_cast<void* volatile*>(&table[7].input),reinterpret_cast<void*>(&RootInput));
        InterlockedExchangePointer(reinterpret_cast<void* volatile*>(&table[7].draw),reinterpret_cast<void*>(&RootDraw));
    }
    if(command->model<2) {
        const bool enabled=command->model==1;
        // Disable only outside our submenu. Its native Back action remains usable.
        for(int i=0;i<10;++i) {
            auto context=reinterpret_cast<unsigned char*>(base+0x1c4c9f0+i*0xf0);
            if(!enabled && registered_index>=0 && field<short>(context,0x14)==registered_index)return 3;
        }
        state.enabled=enabled;
        // A list already open at installation has measured only vanilla rows.
        // The next native draw adds the row and establishes the new bound.
        if(!enabled && state.root_row>=1) {
            for(int i=0;i<10;++i) {
                auto context=reinterpret_cast<unsigned char*>(base+0x1c4c9f0+i*0xf0);
                if(field<short>(context,0x14)!=7)continue;
                auto& selected=field<short>(context,0xa);
                if(selected==state.root_row)selected=0;
                else if(selected>state.root_row)--selected;
                field<short>(context,0x12)=static_cast<short>(state.vanilla_rows-1);
            }
            state.root_row=-1;
        }
    }
    command->found=state.root_draws;
    command->owned=(registered_index>=0 ? 1u : 0u)|(state.enabled ? 2u : 0u);
    return 0;
}
}
