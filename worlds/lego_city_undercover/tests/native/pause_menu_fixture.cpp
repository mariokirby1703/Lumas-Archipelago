// Runs against synthetic menu contexts; never opens or modifies the game.
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <cassert>
#include <string>
#include <vector>
struct Command {unsigned name_hash,model,found,owned,receipt,binding[4];};
static unsigned Hash(const char*) {return 1;}
#include "pause_menu.h"

static int vanilla_inputs=0,pushes=0,pops=0;
static int last_native_selected=-1;
static std::vector<std::string> labels;
static std::vector<int> drawn_rows;
static std::vector<float> drawn_positions;
static void __fastcall Row(unsigned char* c,const char* text) {
    using namespace lcu_pause;
    const int row=field<int>(c,0x98);
    if(row>=field<short>(c,0xe) && row<=field<short>(c,0x12)) {
        labels.emplace_back(text);drawn_rows.push_back(row);drawn_positions.push_back(field<float>(c,0xa4));
    }
    ++field<int>(c,0x98);
    const float spacing=field<float>(c,0xe4);
    field<float>(c,0xa4)+=(spacing ? spacing : *default_row_spacing)*(*native_row_scale);
}
static void __fastcall Dim(unsigned char* c,const char* text,unsigned char) {Row(c,text);}
static void __fastcall OriginalDraw(unsigned char* c) {
    for(const char* text : {"Resume","Return to Police Station","Options","Extras","Quit","Exit to Windows"})Row(c,text);
    lcu_pause::field<short>(c,0x12)=static_cast<short>(lcu_pause::field<int>(c,0x98)-1+lcu_pause::field<short>(c,0xe));
}
static void __fastcall OriginalInput(unsigned char* c) {last_native_selected=lcu_pause::field<int>(c,0x40);++vanilla_inputs;}
static void* __fastcall Push(int id,int selected,int parent) {
    assert(id==lcu_pause::chapter_menu_id && selected==0 && parent==-1);++pushes;return nullptr;
}
static void __fastcall Pop() {++pops;}
int main() {
    using namespace lcu_pause;
    alignas(16) unsigned char contexts[10*0xf0]{};
    image=reinterpret_cast<std::uintptr_t>(contexts)-0x1c4c9f0;
    original_draw=OriginalDraw;original_input=OriginalInput;
    draw_row=Row;draw_dim_row=Dim;push_menu=Push;pop_menu=Pop;
    registered_index=47;state.enabled=true;
    const float native_spacing=row_spacing,scale=1;
    default_row_spacing=&native_spacing;native_row_scale=&scale;resume_text="Resume";
    auto root=contexts+0xf0;field<short>(root,0x14)=7;
    RootDraw(root);
    assert(field<int>(root,0x98)==7 && field<short>(root,0x12)==6 && state.root_row==1);
    assert(labels.size()==7 && labels.back()=="Chapter Select");
    assert(labels[0]=="Return to Police Station" && drawn_rows[0]==2 && drawn_positions[0]==2*row_spacing);
    assert(labels[5]=="Resume" && drawn_rows[5]==0 && drawn_positions[5]==0);
    assert(drawn_rows[6]==1 && drawn_positions[6]==row_spacing);
    field<int>(root,0x40)=1;field<int>(root,0x70)=1;RootInput(root);
    assert(pushes==1 && vanilla_inputs==0);
    field<int>(root,0x40)=2;RootInput(root);assert(vanilla_inputs==1 && last_native_selected==1 && field<int>(root,0x40)==2);
    for(int selected=3;selected<=6;++selected) {
        field<int>(root,0x40)=selected;RootInput(root);
        assert(last_native_selected==selected-1 && field<int>(root,0x40)==selected);
    }
    field<int>(root,0x70)=0;field<int>(root,0x74)=1;RootInput(root);assert(vanilla_inputs==6);
    auto sub=contexts+2*0xf0;field<short>(sub,0x14)=47;
    field<int>(sub,0x70)=1;
    labels.clear();field<int>(sub,0x98)=0;ChaptersDraw(sub);
    assert(labels.size()==15 && labels.front()=="Chapter 1" && labels.back()=="Chapter 15");
    assert(field<short>(sub,0x12)==14 && field<float>(sub,0xe0)==0.50f && field<float>(sub,0xe4)==row_spacing);
    assert(row_position(0,0)==0 && row_position(14,14)==0);
    assert(row_alpha(14,0,48)==0 && row_alpha(14,14,48)==48 && row_alpha(15,15,128)==128);
    assert(row_alpha(2,0,128)>0 && row_alpha(2,0,128)<128);
    field<short>(sub,0xa)=14;labels.clear();field<int>(sub,0x98)=0;ChaptersDraw(sub);
    assert(labels.size()==15 && field<short>(sub,0x12)==14);
    for(int i=0;i<15;++i) {field<int>(sub,0x40)=i;ChaptersInput(sub);assert(pops==0);}
    field<int>(sub,0x40)=15;ChaptersInput(sub);assert(pops==0);
    field<int>(sub,0x70)=0;field<int>(sub,0x74)=1;ChaptersInput(sub);assert(pops==1);
    state.enabled=false;labels.clear();field<int>(root,0x98)=0;RootDraw(root);
    assert(labels.size()==6 && labels[0]=="Resume" && field<int>(root,0x98)==6);
    return 0;
}
