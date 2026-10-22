"""Execute actual scattered PPC (not a Python reimplementation of the gates)."""
import struct
import pytest
from ..client import native_events as n
from .test_memory import FakeBackend


class Machine:
    def __init__(self,kind):
        self.b=FakeBackend();self.control=0x80002e00;self.kind=kind
        self.r=[0x80010000+i*0x100 for i in range(32)]
        self.r[0]=1;self.r[1]=0x90100000;self.r[2]=0x808fc5c0
        self.f=[float(i) for i in range(32)];self.lr=0x80001234;self.ctr=0x80005678;self.cr=0x12345678;self.cmp=0
        self.stage=0x90010000;self.player=0x90020000;self.machine=0x90030000;self.input=0x90040000;self.event=0x90050000
        self.calls=[];self.call_targets=[]
        for a,o,b in n.patches(self.control):self.b.put(a,b)
        self.b.put(self.control,bytes(n.SIZE));self.put(self.control,n.MAGIC)
        for i in range(4):self.put(self.control+n.JUMP_TABLE+i*4,sum(1<<(s%32) for s in n.JUMP_STATES if s//32==i))
        self.put(self.control+n.STAGE,self.stage);self.put(self.control+n.PLAYER,self.player)
        self.put(self.control+n.SERIAL,123);self.put(self.control+n.INPUT,self.input)
        self.put(self.control+n.ENABLE,1)
        self.put(self.player,0x8075aef8);self.put(self.player+12,123)
        self.put(self.player+0x88,self.input)
        self.put(self.stage+0x114,0x90060000);self.put(0x90060038,123)
        self.put(self.stage+0x44,0x8001cdb4);self.put(self.player+0x70,0x90070000)
        self.put(0x90070008,self.machine);self.put(self.machine,0x8075a0f8)
        self.put(self.machine+0x28,self.player);self.put(self.machine+0x1c,3)
        self.put(0x808f336c,0x90080000);self.put(0x90080004,0x90081000)
        self.put(0x9008101c,0x90082000);self.put(0x90082034,self.stage)
        self.put(0x808f6040,0);self.put(self.event+4,struct.unpack('>I',struct.pack('>f',.5))[0])
        self.r[29]=self.stage;self.r[30]=self.event;self.r[4]=self.stage
        if kind=='music':
            self.r[31]=0x90090020;self.r[30]=0x900a0000
            self.b.put(0x90090000,b'bgm_wmap'.ljust(32,b'\0'));self.put(0x90090020,100)
        if kind=='music_loop':
            self.put(self.control+n.CHANNEL,0x900a0000);self.put(self.control+n.CUE,1002)
        if kind=='jump':self.r[3]=self.input;self.r[4]=2;self.r[5]=0
        if kind=='jump_state':self.r[3]=self.machine+0x14;self.r[4]=5;self.r[1]-=0xc0
        self.before=self.r[:];self.before_f=self.f[:]

    def put(self,a,v):self.b.put(a,(v&0xffffffff).to_bytes(4,'big'))
    def get(self,a):return int.from_bytes(self.read(a,4),'big')
    def read(self,a,size):
        assert 0x80000000<=a<a+size<=0x94000000,f'invalid native read {a:#x}'
        return self.b.read_bytes(a,size)
    def run(self):
        pc=n.HOOKS[self.kind][0]
        for _ in range(4000):
            if pc in (n.HOOKS[self.kind][0]+4,0x80001234):return
            w=self.get(pc);next_pc=pc+4;op=w>>26;rt=w>>21&31;ra=w>>16&31;rb=w>>11&31;u=w&65535;imm=u-65536 if u&32768 else u
            if op==14:self.r[rt]=((self.r[ra] if ra else 0)+imm)&0xffffffff
            elif op==15:self.r[rt]=(imm<<16)&0xffffffff
            elif op==24:self.r[ra]=self.r[rt]|u
            elif op==28:
                self.r[ra]=self.r[rt]&u;self.cmp=(self.r[ra]>0)
            elif op==32:self.r[rt]=self.get((self.r[ra]+imm)&0xffffffff)
            elif op==34:self.r[rt]=self.read((self.r[ra]+imm)&0xffffffff,1)[0]
            elif op in (36,37,38):
                a=(self.r[ra]+imm)&0xffffffff;size=1 if op==38 else 4
                self.b.write_bytes(a,(self.r[rt]&((1<<(8*size))-1)).to_bytes(size,'big'))
                if op==37:self.r[ra]=a
            elif op in (46,47):
                if op==46:assert ra<rt, 'invalid lmw: base register is in load range'
                a=self.r[ra]+imm
                for r in range(rt,32):
                    if op==47:self.put(a+4*(r-rt),self.r[r])
                    else:self.r[r]=self.get(a+4*(r-rt))
            elif op in (48,50):self.f[rt]=struct.unpack('>f' if op==48 else '>d',self.read(self.r[ra]+imm,4 if op==48 else 8))[0]
            elif op in (52,54):self.b.write_bytes(self.r[ra]+imm,struct.pack('>f' if op==52 else '>d',self.f[rt]))
            elif op==11:
                v=self.r[ra];v=v-(1<<32) if v>>31 else v
                self.cmp=(v>imm)-(v<imm)
            elif op==10:self.cmp=(self.r[ra]>u)-(self.r[ra]<u)
            elif op==16:
                take={0x41820000:self.cmp==0,0x40820000:self.cmp!=0,0x41800000:self.cmp<0,
                      0x40800000:self.cmp>=0,0x41810000:self.cmp>0,0x40810000:self.cmp<=0}[w&0xffff0000]
                if take:next_pc=pc+imm
            elif op==18:
                delta=w&0x3fffffc
                if delta&0x2000000:delta-=0x4000000
                if w&1:self.lr=pc+4
                next_pc=(pc+delta)&0xffffffff
            elif w==0x7c000026:self.r[0]=self.cr
            elif w==0x7c0802a6:self.r[0]=self.lr
            elif w==0x7c0902a6:self.r[0]=self.ctr
            elif w==0x7c0ff120:self.cr=self.r[0]
            elif w==0x7c0803a6:self.lr=self.r[0]
            elif w==0x7c0903a6:self.ctr=self.r[0]
            elif w==0x7d8903a6:self.ctr=self.r[12]
            elif w==0x4e800421:
                callback=getattr(self,'native_call',None)
                if callback is None:
                    assert self.ctr in ((0x801251ec,0x80125310,0x80125390) if self.kind=='music_loop' else (0x800338e8,))
                self.call_targets.append(self.ctr)
                self.calls.append((self.r[3],self.r[4]))
                result=callback(self.ctr) if callback else None
                self.lr=pc+4;self.cr=0xabcdef01
                for r in (0,*range(3,13)):self.r[r]=0xdddddddd
                for f in range(14):self.f[f]=-999.
                self.ctr=0xcccccccc
                if result is not None:self.r[3]=result
            elif w==0x4e800020:next_pc=self.lr
            elif w==0xec000828:self.f[0]-=self.f[1]
            elif w==0xec210028:self.f[1]-=self.f[0]
            elif w==0xec21002a:self.f[1]+=self.f[0]
            elif w==0xfc400890:self.f[2]=self.f[1]
            elif w==0xfc001040:self.cmp=(self.f[0]>self.f[2])-(self.f[0]<self.f[2])
            elif w==0xfc001090:self.f[0]=self.f[2]
            elif w==0x5484103a:self.r[4]=(self.r[4]<<2)&0xffffffff
            elif op==21:
                sh=w>>11&31;mb=w>>6&31;me=w>>1&31;value=self.r[rt]
                rotated=((value<<sh)|(value>>(32-sh if sh else 32)))&0xffffffff
                mask=sum(1<<(31-i) for i in range(mb,me+1));self.r[ra]=rotated&mask
            elif w in (0x60000000,0x7c0004ac):pass
            elif op==31 and w&0x7ff==0:self.cmp=(self.r[ra]>self.r[rb])-(self.r[ra]<self.r[rb])
            elif op==31 and w&0x7ff==0x378:self.r[ra]=self.r[rt]|self.r[rb]
            elif op==31 and w&0x7ff==46:self.r[rt]=self.get(self.r[ra]+self.r[rb])
            elif op==31 and w&0x7ff==48:self.r[ra]=(self.r[rt]<<(self.r[rb]&63))&0xffffffff
            elif op==31 and w&0x7ff==0x1d6:self.r[rt]=(self.r[ra]*self.r[rb])&0xffffffff
            elif op==31 and w&0x7ff==0x214:self.r[rt]=(self.r[ra]+self.r[rb])&0xffffffff
            elif op==31 and w&0x7ff in (56,57):
                self.r[ra]=self.r[rt]&self.r[rb]
                if w&1:self.cmp=(self.r[ra]>0)
            else:raise AssertionError(f'{pc:#x}: {w:#x}')
            pc=next_pc
        raise AssertionError('native program did not terminate')


def test_death_event_is_published_at_real_native_counter_write():
    m=Machine('death');m.run()
    assert m.get(m.control+n.DEATH_SEQ)==2
    assert m.get(m.control+n.DEATH_STAGE)==m.stage
    assert m.get(m.control+n.DEATH_COUNT)==m.get(m.stage+0x468)==0
    assert m.r==m.before and m.lr==0x80001234 and m.ctr==0x80005678 and m.cr==0x12345678


def test_successful_bgm_start_copies_bounded_identity_and_ignores_sfx():
    m=Machine('music');m.run()
    assert m.get(m.control+n.MUSIC_SEQ)==2
    assert m.read(m.control+n.NAME,8)==b'bgm_wmap'
    assert m.r==m.before
    m=Machine('music');m.b.put(0x90090000,b'se_jump\0');m.run()
    assert m.get(m.control+n.MUSIC_SEQ)==0


@pytest.mark.parametrize('state',[3,24,25,26,65,112])
def test_remote_kill_calls_native_dead_once_only_in_safe_state(state):
    m=Machine('frame');m.put(m.control+n.REQUEST,1);m.put(m.machine+0x1c,state)
    m.run()
    assert m.calls==([(m.machine,24)] if state==3 else [])
    expected=m.before[:];expected[0]=m.get(m.stage+0xa4)  # displaced native load
    assert m.f==m.before_f and m.r==expected and m.cr==0x12345678 and m.ctr==0x80005678
    m.run();assert len(m.calls)==int(state==3)


def test_countdown_uses_native_gameplay_delta_and_acks_then_clamps_zero():
    m=Machine('frame');m.put(m.control+n.REMAINING,0x3f800000);m.put(m.control+n.TRAP_REQUEST,7)
    m.run();assert struct.unpack('>f',m.read(m.control+n.REMAINING,4))[0]==.5
    assert m.get(m.control+n.TRAP_ACK)==7
    m.run();m.run();assert m.get(m.control+n.REMAINING)==0
    m=Machine('frame');m.put(m.control+n.ENABLE,0);m.put(m.control+n.REMAINING,0x3f800000)
    m.run();assert m.get(m.control+n.REMAINING)==0x3f800000


@pytest.mark.parametrize('action,remaining,match,blocked',[(0,30,True,True),(1,30,True,False),(0,0,True,False),(0,30,False,False)])
def test_jump_query_suppression_is_scoped_and_reversible(action,remaining,match,blocked):
    m=Machine('jump');m.r[5]=action
    if not match:m.r[3]+=0x100
    m.put(m.control+n.REMAINING,struct.unpack('>I',struct.pack('>f',remaining))[0]);m.run()
    assert (m.r[3]==0)==blocked


def test_reused_input_pointer_cannot_lock_a_replaced_player():
    m=Machine('jump');m.put(m.control+n.REMAINING,0x41f00000)
    m.put(m.player+12,456);m.run()
    assert m.r[3]==m.input


def test_jump_block_uses_fresh_controller_after_respawn():
    m=Machine('jump');replacement=m.input+0x100
    m.put(m.player+0x88,replacement);m.r[3]=replacement
    m.put(m.control+n.REMAINING,0x41700000)
    m.run();assert m.r[3]==0


@pytest.mark.parametrize('handler',[0,0x80010000])
def test_results_and_other_non_gameplay_handlers_preserve_trap_time(handler):
    m=Machine('frame');m.put(m.stage+0x44,handler)
    m.put(m.control+n.REMAINING,0x41700000)
    m.run();assert m.get(m.control+n.REMAINING)==0x41700000


def test_fifteen_native_gameplay_seconds_expire_even_without_host_polling():
    m=Machine('frame');m.put(m.control+n.REMAINING,0x41700000)
    for _ in range(29):m.run()
    assert struct.unpack('>f',m.read(m.control+n.REMAINING,4))[0]==.5
    m.run();assert m.get(m.control+n.REMAINING)==0


@pytest.mark.parametrize('state',n.JUMP_STATES)
def test_all_registered_jump_requests_are_denied_without_entry_callbacks(state):
    m=Machine('jump_state');m.r[4]=state;m.put(m.control+n.REMAINING,0x41f00000)
    m.run()
    assert m.r[1]==m.before[1]+0xc0 and m.lr==0x80001234
    assert m.r[4]==state and not m.calls


@pytest.mark.parametrize('state',[3,4,16,24,25,38,67,88,100,112])
def test_non_jump_requests_and_native_death_are_not_trapped(state):
    m=Machine('jump_state');m.r[4]=state;m.put(m.control+n.REMAINING,0x41f00000)
    m.run()
    assert m.r[1]==m.before[1] and m.r[0]==0x80001234


@pytest.mark.parametrize('pause_flags',[0x400,0x800,0xc00])
def test_paused_gameplay_neither_consumes_trap_time_nor_acknowledges_death(pause_flags):
    m=Machine('frame');m.put(m.stage+0xa4,pause_flags)
    m.put(m.control+n.REMAINING,0x41f00000);m.put(m.control+n.REQUEST,1)
    m.run()
    assert m.get(m.control+n.REMAINING)==0x41f00000
    assert not m.calls and m.get(m.control+n.ACK)==0


def test_dead_weight_and_remote_death_overlap_without_repeating_death_request():
    m=Machine('frame');m.put(m.control+n.REMAINING,0x41f00000)
    m.put(m.control+n.TRAP_REQUEST,9);m.put(m.control+n.REQUEST,7)
    m.run();m.run()
    assert len(m.calls)==1 and m.get(m.control+n.ACK)==7
    assert m.get(m.control+n.TRAP_ACK)==9
    assert struct.unpack('>f',m.read(m.control+n.REMAINING,4))[0]==29.


@pytest.mark.parametrize('field,value',[('serial',456),('stage',0x90010100),('player_vtable',0x8075a000)])
def test_stale_actor_context_cannot_consume_a_native_effect(field,value):
    m=Machine('frame');m.put(m.control+n.REMAINING,0x41f00000);m.put(m.control+n.REQUEST,7)
    if field=='serial':m.put(m.player+12,value)
    if field=='stage':m.put(m.control+n.STAGE,value)
    if field=='player_vtable':m.put(m.player,value)
    m.run()
    assert not m.calls and m.get(m.control+n.ACK)==0
    assert m.get(m.control+n.REMAINING)==0x41f00000


@pytest.mark.parametrize('blocked',[None,'playing','paused','error','disabled','unowned','not_started','stopping','other_cue','no_descriptor','unarmed','other_channel','new_cue_same_channel'])
def test_finite_song_restart_uses_native_end_and_preserves_registers(blocked):
    m=Machine('music_loop');channel=0x900a0000;descriptor=0x90090020
    m.r[3]=4;m.r[30]=channel;m.put(channel,1);m.put(channel+8,descriptor)
    m.b.put(channel+0x28,b'\0\1');m.put(descriptor,1002);m.put(m.control+n.LOOP_CUE,0x10000|1002)
    if blocked=='unarmed':m.put(m.control+n.LOOP_CUE,1002)
    if blocked=='playing':m.r[3]=2
    if blocked=='paused':m.r[3]=3
    if blocked=='error':m.r[3]=5
    if blocked=='disabled':m.put(m.control+n.LOOP_CUE,0)
    if blocked=='unowned':m.put(channel,0)
    if blocked=='not_started':m.b.put(channel+0x29,b'\0')
    if blocked=='stopping':m.b.put(channel+0x28,b'\2')
    if blocked=='other_cue':m.put(descriptor,2001)
    if blocked=='no_descriptor':m.put(channel+8,0)
    if blocked=='other_channel':m.put(m.control+n.CHANNEL,channel+0x100)
    if blocked=='new_cue_same_channel':m.put(m.control+n.CUE,2001)
    before=m.r[:];m.run()
    assert m.calls==([(channel,0),(channel,descriptor),(channel,0)] if blocked is None else [])
    if blocked is None:assert m.call_targets==[0x801251ec,0x80125310,0x80125390]
    before[0]=(before[3]-1)&0xffffffff # displaced native addi r0,r3,-1
    assert m.r==before and m.f==m.before_f
    assert (m.lr,m.ctr,m.cr)==(0x80001234,0x80005678,0x12345678)


def test_restart_latch_waits_for_playing_before_another_end():
    m=Machine('music_loop');channel=0x900a0000;descriptor=0x90090020
    m.r[3]=4;m.r[30]=channel;m.put(channel,1);m.put(channel+8,descriptor)
    m.b.put(channel+0x28,b'\0\1');m.put(descriptor,1002)
    m.put(m.control+n.LOOP_CUE,0x10000|1002)
    m.run();assert len(m.calls)==3
    assert m.get(m.control+n.LOOP_CUE)==1002
    for state in (4,1,4,1,4):
        m.r[3]=state;m.run();assert len(m.calls)==3
    m.r[3]=2;m.run();assert m.get(m.control+n.LOOP_CUE)==0x10000|1002
    m.r[3]=4;m.run();assert len(m.calls)==6


def test_temporary_music_cannot_replay_or_arm_the_suspended_finite_song():
    m=Machine('music_loop');channel=0x900a0000;descriptor=0x90090020
    m.r[30]=channel;m.put(channel,1);m.put(channel+8,descriptor)
    m.b.put(channel+0x28,b'\0\1');m.put(descriptor,1002)
    m.put(m.control+n.LOOP_CUE,0x10000|1002)
    # The guest already started Wisp music, while the host still has old policy.
    m.put(m.control+n.CHANNEL,channel+0x100);m.put(m.control+n.CUE,2001)
    for state in (3,4,4,2,4):m.r[3]=state;m.run()
    assert not m.calls
    # Returning paused/preparing is not proof the finite stream played again.
    m.put(m.control+n.CHANNEL,channel);m.put(m.control+n.CUE,1002)
    m.put(m.control+n.LOOP_CUE,1002)
    for state in (1,3,4):m.r[3]=state;m.run()
    assert not m.calls
    m.r[3]=2;m.run();m.r[3]=4;m.run()
    assert len(m.calls)==3 # actual end after resumed playback still loops


def test_successful_music_change_clears_previous_end_latch_in_guest():
    m=Machine('music');m.put(m.control+n.LOOP_CUE,0x10000|1002)
    m.run()
    assert m.get(m.control+n.LOOP_CUE)==1002
