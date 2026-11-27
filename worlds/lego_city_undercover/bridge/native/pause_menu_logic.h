// Immediate-mode list state. No gameplay, inventory or save mutations.
namespace lcu_pause {
constexpr int chapter_menu_id=0x41504348; // APCH, distinct from all 47 vanilla IDs.
constexpr int chapter_rows=15;
constexpr int rows=chapter_rows;
constexpr float row_spacing=-0.10664000362157822f;
// Original Extras 0x7f0a10 / 0x7f0f99 centers the selected row and fades
// rows between absolute Y 0.15 and 0.60; native input keeps all rows reachable.
inline float row_position(int row,int selected) {return (row-selected)*row_spacing;}
inline unsigned char row_alpha(int row,int selected,unsigned char maximum) {
    float distance=row_position(row,selected);
    if(distance<0)distance=-distance;
    if(distance>=0.60f)return 0;
    if(distance<=0.15f)return maximum;
    return static_cast<unsigned char>(maximum*(0.60f-distance)/(0.60f-0.15f));
}

struct State {
    bool enabled=false;
    int root_row=-1;
    int vanilla_rows=0;
    unsigned root_draws=0,chapter_draws=0;
};

enum class Action { None, Back, Unavailable };
inline Action action(int selected,bool confirm,bool back) {
    if(back)return Action::Back;
    if(!confirm)return Action::None;
    if(selected>=0 && selected<chapter_rows)return Action::Unavailable;
    return Action::None;
}
}
