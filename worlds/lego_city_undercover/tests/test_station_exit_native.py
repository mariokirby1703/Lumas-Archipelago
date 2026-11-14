"""Execute the native exit guard against synthetic memory, never a game process."""
import ctypes
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import unittest

@unittest.skipUnless(sys.platform=='win32' and platform.machine().lower() in ('amd64','x86_64'),'Windows x64')
class NativeStationExitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[3];out=root/'build/lego_city_undercover';out.mkdir(parents=True,exist_ok=True)
        sys.path.insert(0,str(root/'worlds/lego_city_undercover/bridge'))
        from native_context_policy import header
        (out/'native_context_policy.h').write_text(header(),encoding='utf-8')
        dll=out/'StationExitTest.dll'
        result=subprocess.run([sys.executable,'-m','ziglang','c++','-target','x86_64-windows-gnu',
            '-shared','-O2','-I',str(out),str(Path(__file__).parent/'native/station_exit_fixture.cpp'),'-o',str(dll)],
            capture_output=True,text=True,env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'zig-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'zig-local-cache')))
        if result.returncode:raise RuntimeError(result.stderr)
        cls.dll=ctypes.WinDLL(str(dll));cls.invoke=cls.dll.TestStationExit
        cls.invoke.argtypes=[ctypes.c_size_t,ctypes.c_size_t,ctypes.POINTER(ctypes.c_uint32)]
        cls.invoke.restype=ctypes.c_uint32
        cls.lift=cls.dll.TestLobbyLift
        cls.lift.argtypes=cls.invoke.argtypes;cls.lift.restype=ctypes.c_uint32
        cls.fields=cls.dll.TestTutorialFields
        cls.fields.argtypes=cls.invoke.argtypes;cls.fields.restype=ctypes.c_uint32
        cls.chief=cls.dll.TestChiefKey
        cls.chief.argtypes=cls.invoke.argtypes;cls.chief.restype=ctypes.c_uint32
        cls.radio=cls.dll.TestChiefRadio
        cls.radio.argtypes=cls.invoke.argtypes;cls.radio.restype=ctypes.c_uint32
        cls.local_currency=cls.dll.TestLocalCurrency
        cls.local_currency.argtypes=[ctypes.c_size_t,ctypes.c_uint32,ctypes.c_uint32];cls.local_currency.restype=ctypes.c_uint32
        cls.local_remove=cls.dll.TestLocalRemove
        cls.local_remove.argtypes=[ctypes.c_size_t,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32];cls.local_remove.restype=ctypes.c_uint32
        cls.claim=cls.dll.ClaimPacket
        cls.claim.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32]
        cls.claim.restype=ctypes.c_uint32
    def setUp(self):
        self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        self.k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong,ctypes.c_ulong]
        self.k.VirtualAlloc.restype=ctypes.c_void_p
        self.k.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong]
        self.base=self.k.VirtualAlloc(None,0x2100000,0x3000,0x40)
        if not self.base:raise ctypes.WinError(ctypes.get_last_error())
        self.actor=self.base+0x2000000;self.registry=self.actor+0x1000;self.entry=self.actor+0x2000
        self.owner=self.actor+0x3000;self.tile=self.actor+0x4000;self.level=self.actor+0x5000
        self.data=self.actor+0x6000;self.table=self.actor+0x7000;self.manager=self.actor+0x8000
        self.door=self.actor+0x9000;self.actor_vt=self.actor+0xa000;self.scene_name=self.actor+0xb000
        self.counter=ctypes.c_uint32()
        from research_profile import symbol_hash
        system=self.actor+0xc000;job_table=self.actor+0xd000
        ctypes.c_uint64.from_address(self.base+0x17eca08).value=system
        ctypes.c_uint64.from_address(system+0xe0).value=job_table
        ctypes.c_uint32.from_address(system+0xe8).value=4
        jobs=[('Flow_Setup',[('Flow_Act',1,False)]),
              ('Flow_Setup.Act_1',[('Act1_Mission',1,False),('Act1_Stage',2,False)]),
              ('Flow_Setup.Act_1.LCPD.LCPD_Level.LCPD_Lobby',
               [('LCPD_LobbyEntered',1,False),('LCPD_MainframeActive',0,True)]),
              ('PDA',[('acquired',0,True)])]
        self.job_values={};value_index=0
        for i,(name,fields) in enumerate(jobs):
            array=self.actor+0xe000+i*0x100
            record=struct.pack('<I4xQH6x',symbol_hash(name),array,len(fields))
            ctypes.memmove(job_table+i*24,record,len(record))
            for j,(field,value,is_bool) in enumerate(fields):
                obj=self.actor+0xf000+value_index*0x100;value_index+=1
                ctypes.c_uint64.from_address(array+j*8).value=obj
                ctypes.c_uint64.from_address(obj).value=self.base+(0xc46bb8 if is_bool else 0xc46b38)
                ctypes.c_uint32.from_address(obj+12).value=symbol_hash(field)
                ctypes.c_uint32.from_address(obj+16).value=value
                self.job_values[field]=obj+16

        for address,value in ((self.base+0x1c402d8,self.registry),(self.registry+0x18,self.entry),
            (self.entry+0xd8,self.owner),(self.owner+0xb18,self.tile),(self.tile+0x68,self.scene_name),
            (self.owner+0xbb0,self.level),(self.level+0xa0,self.data),(self.data+0xc0,self.table),
            (self.table+18*8,self.manager),(self.manager,self.base+0xd603f8),(self.manager+0xe0,self.door),
            (self.door,self.base+0xd5fc98),(self.door+0x48,self.manager),(self.actor+0x10,self.actor_vt),
            (self.actor_vt+0xf0,self.base+0x49ecf0),(self.base+0xd5fc98+0x210,self.base+0x8a1780)):
            ctypes.c_uint64.from_address(address).value=value
        ctypes.memmove(self.scene_name,b'Police_Station_Lobby\0',21)
        name=b'POLICE_LOBBY_EXTERNAL_DOOR\0';ctypes.memmove(self.door+0x58,name,len(name))
        # Native signature plus a harmless test-only counter increment and return.
        code=bytes.fromhex('40 53 48 83 ec 30 48 b8')+struct.pack('<Q',ctypes.addressof(self.counter))+bytes.fromhex('ff 00 48 83 c4 30 5b c3')
        ctypes.memmove(self.base+0x8a1780,code,len(code))
    def tearDown(self):self.k.VirtualFree(self.base,0,0x8000)
    def call(self):
        triggered=ctypes.c_uint32();code=self.invoke(self.base,self.actor,ctypes.byref(triggered))
        return code,triggered.value
    def test_valid_lobby_calls_exact_existing_door_trigger(self):
        self.assertEqual(self.call(),(0,1));self.assertEqual(self.counter.value,1)
    def test_other_scene_or_distant_actor_cannot_trigger(self):
        ctypes.memmove(self.scene_name,b'Lego_City\0',10)
        self.assertEqual(self.call(),(0,0))
        ctypes.memmove(self.scene_name,b'Police_Station_Lobby\0',21)
        ctypes.c_float.from_address(self.actor+0x1f0).value=1.2
        self.assertEqual(self.call(),(0,0));self.assertEqual(self.counter.value,0)
    def test_wrong_door_owner_cycle_and_signature_rejected(self):
        ctypes.c_uint64.from_address(self.door+0x48).value=0
        self.assertEqual(self.call(),(5,0))
        ctypes.c_uint64.from_address(self.door+0x48).value=self.manager
        ctypes.c_uint64.from_address(self.door+0x28).value=self.door
        self.assertEqual(self.call(),(5,0))
        ctypes.c_uint64.from_address(self.door+0x28).value=0
        ctypes.c_ubyte.from_address(self.base+0x8a1780).value=0x90
        self.assertEqual(self.call(),(1,0));self.assertEqual(self.counter.value,0)

    def test_real_hook_packet_claim_accepts_station_exit_exactly_once(self):
        for opcode in (*range(1,11),12,13,14,15,16,17,18):
            packet=(ctypes.c_uint32*16)()
            packet[0]=0x4c435549;packet[1]=2;packet[2]=1;packet[3]=opcode
            packet[4]=77;packet[5]=88
            self.assertEqual(self.claim(packet,77,88),1)
            self.assertEqual(packet[2],2)
            self.assertEqual(self.claim(packet,77,88),0)
    def test_real_hook_packet_claim_rejects_unknown_opcode_and_wrong_identity(self):
        for opcode,pid,thread in ((11,77,88),(99,77,88),(12,76,88),(12,77,89)):
            packet=(ctypes.c_uint32*16)()
            packet[0]=0x4c435549;packet[1]=2;packet[2]=1;packet[3]=opcode
            packet[4]=77;packet[5]=88
            self.assertEqual(self.claim(packet,pid,thread),0)
            self.assertEqual(packet[2],1)

    def test_reentry_counter_is_prepared_without_advancing_mainframe_or_mission(self):
        for old_count in (1,2,1):
            ctypes.c_uint32.from_address(self.job_values['LCPD_LobbyEntered']).value=old_count
            self.assertEqual(self.call(),(0,1))
            self.assertEqual(ctypes.c_uint32.from_address(self.job_values['LCPD_LobbyEntered']).value,0)
            self.assertEqual(ctypes.c_uint32.from_address(self.job_values['Act1_Mission']).value,1)
            self.assertEqual(ctypes.c_uint32.from_address(self.job_values['Act1_Stage']).value,2)
            self.assertEqual(ctypes.c_uint32.from_address(self.job_values['LCPD_MainframeActive']).value,0)
    def test_unknown_or_later_tutorial_phase_cannot_change_counter_or_exit(self):
        for field,value in (('Act1_Mission',2),('LCPD_LobbyEntered',3)):
            original=ctypes.c_uint32.from_address(self.job_values[field]).value
            ctypes.c_uint32.from_address(self.job_values[field]).value=value
            self.assertEqual(self.call(),(16,0))
            self.assertEqual(ctypes.c_uint32.from_address(self.job_values[field]).value,value)
            ctypes.c_uint32.from_address(self.job_values[field]).value=original
        self.assertEqual(self.counter.value,0)

    def test_repaired_mainframe_during_first_visit_preserves_first_visit_and_flag(self):
        ctypes.c_uint32.from_address(self.job_values['LCPD_MainframeActive']).value=1
        self.assertEqual(self.call(),(0,1))
        self.assertEqual(ctypes.c_uint32.from_address(self.job_values['LCPD_LobbyEntered']).value,0)
        self.assertEqual(ctypes.c_uint32.from_address(self.job_values['LCPD_MainframeActive']).value,1)
        ctypes.c_uint32.from_address(self.job_values['LCPD_LobbyEntered']).value=2
        self.assertEqual(self.call(),(16,0))
        self.assertEqual(ctypes.c_uint32.from_address(self.job_values['LCPD_LobbyEntered']).value,2)
    def prepare_garage(self):
        name=b'Police_Station_Garage\0';ctypes.memmove(self.scene_name,name,len(name))
        name=b'POLICE_GARAGE_DOOR\0';ctypes.memmove(self.door+0x58,name,len(name))
        self.bank=self.actor+0x16000
        ctypes.c_uint64.from_address(self.base+0x1c7cbb8).value=self.bank
        ctypes.c_uint32.from_address(self.job_values['LCPD_MainframeActive']).value=1
        # Accessible point in front of the closed lift, 1.2 m from its anchor.
        ctypes.c_float.from_address(self.actor+0x1f0).value=-1.2
    def test_garage_lift_returns_without_police_and_preserves_first_lobby(self):
        self.prepare_garage()
        self.assertEqual(self.call(),(0,1))
        self.assertEqual(self.counter.value,1)
        self.assertEqual(ctypes.c_uint32.from_address(self.job_values['LCPD_LobbyEntered']).value,0)
        self.assertEqual(ctypes.c_uint32.from_address(self.job_values['LCPD_MainframeActive']).value,1)
        self.assertEqual(ctypes.c_ubyte.from_address(self.bank+0x80+227).value,0)
    def test_garage_lift_does_not_override_owned_police_or_distant_player(self):
        self.prepare_garage()
        ctypes.c_ubyte.from_address(self.bank+0x80+227).value=1
        self.assertEqual(self.call(),(0,0))
        self.assertEqual(ctypes.c_uint32.from_address(self.job_values['LCPD_LobbyEntered']).value,1)
        ctypes.c_ubyte.from_address(self.bank+0x80+227).value=0
        ctypes.c_float.from_address(self.actor+0x1f0).value=-2.0
        self.assertEqual(self.call(),(0,0));self.assertEqual(self.counter.value,0)

    def prepare_lobby_lift(self):
        self.obstacles=self.actor+0x17000;self.opening=self.actor+0x18000;self.closing=self.actor+0x19000
        for address,value in ((self.table+8,self.obstacles),(self.obstacles,self.base+0xc2e468),
            (self.obstacles+0xe0,self.opening),(self.opening,self.base+0xc2dec8),
            (self.closing,self.base+0xc2dec8),(self.opening+0x48,self.obstacles),
            (self.closing+0x48,self.obstacles),(self.opening+0x28,self.closing),
            (self.opening+0x108,self.base+0xc1ba18),(self.closing+0x108,self.base+0xc1ba18)):
            ctypes.c_uint64.from_address(address).value=value
        for obj,name in ((self.opening,b'DoorsOpening'),(self.closing,b'DoorsClosing')):
            ctypes.memmove(obj+0x58,name+b'\0',len(name)+1)
        ctypes.c_uint32.from_address(self.closing+0x128).value=1
        code=bytes.fromhex('48 89 5c 24 08 57 48 83 ec 20 89 51 20 48 83 c4 20 5f 48 8b 5c 24 08 c3')
        ctypes.memmove(self.base+0x77d3e0,code,len(code))
    def call_lift(self):
        opened=ctypes.c_uint32();result=self.lift(self.base,self.actor,ctypes.byref(opened))
        return result,opened.value
    def test_first_lobby_lift_opens_without_transition_or_story_writes(self):
        self.prepare_lobby_lift()
        self.assertEqual(self.call_lift(),(0,1))
        self.assertEqual(ctypes.c_uint32.from_address(self.opening+0x128).value,1)
        self.assertEqual(ctypes.c_uint32.from_address(self.closing+0x128).value,0)
        self.assertEqual(ctypes.c_uint32.from_address(self.job_values['LCPD_LobbyEntered']).value,1)
        self.assertEqual(self.counter.value,0)
    def test_lift_open_rejects_wrong_room_distance_and_unsupported_visit(self):
        self.prepare_lobby_lift()
        ctypes.c_float.from_address(self.actor+0x1f0).value=2
        self.assertEqual(self.call_lift(),(0,0))
        ctypes.c_float.from_address(self.actor+0x1f0).value=0
        name=b'Police_Station_Garage\0';ctypes.memmove(self.scene_name,name,len(name))
        self.assertEqual(self.call_lift(),(0,0))
        name=b'Police_Station_Lobby\0';ctypes.memmove(self.scene_name,name,len(name))
        ctypes.c_uint32.from_address(self.job_values['LCPD_LobbyEntered']).value=2
        self.assertEqual(self.call_lift(),(16,0))
        self.assertEqual(ctypes.c_uint32.from_address(self.opening+0x128).value,0)

    def prepare_tutorial_fields(self,garage=True,discovered=True,acquired=False):
        from research_profile import symbol_hash
        ctypes.c_int32.from_address(self.base+0x1176600).value=580
        name=b'Police_Station_Garage\0' if garage else b'Police_Station_Lobby\0'
        ctypes.memmove(self.scene_name,name,len(name))
        self.bank=self.actor+0x16000
        ctypes.c_uint64.from_address(self.base+0x1c7cbb8).value=self.bank
        if discovered:ctypes.c_ubyte.from_address(self.bank+227//8).value=1<<(227%8)
        system=self.actor+0x27000;component=self.actor+0x28000;self.pad=self.actor+0x29000
        self.other_pad=self.actor+0x2a000
        for address,value in ((self.base+0x17ec098,system),(system,self.base+0xc34ae8),
            (self.table+10*8,component),(component,self.base+0xc34ed8),(component+0xe0,self.pad),
            (self.pad,self.base+0xc34578),(self.pad+0x48,component),(self.pad+0x28,self.other_pad),
            (self.other_pad,self.base+0xc34578),(self.other_pad+0x48,component)):
            ctypes.c_uint64.from_address(address).value=value
        ctypes.c_int32.from_address(system+0xf4).value=10
        for obj,name in ((self.pad,b'#cg_248_Cop_UseKeypad_SW' if garage else b'MF_Switch'),
                         (self.other_pad,b'#cg_221_AXE_DOOR_SWITCH')):
            ctypes.memmove(obj+0x58,name+b'\0',len(name)+1)
            ctypes.c_uint16.from_address(obj+0x8a).value=0x1007
            ctypes.c_uint32.from_address(obj+0x278).value=0x200
        ctypes.c_uint32.from_address(self.pad+0x24c).value=0x10100000 if garage else 0x10000000
        ctypes.c_uint32.from_address(self.other_pad+0x24c).value=0x110200
        ctypes.memmove(self.pad+0x22c,struct.pack('<3f',5.5669465,-0.178157,-3.9803517),12)
        sysobj=ctypes.c_uint64.from_address(self.base+0x17eca08).value
        jobtable=ctypes.c_uint64.from_address(sysobj+0xe0).value
        ctypes.c_uint32.from_address(sysobj+0xe8).value=4
        array=self.actor+0x23000;obj=self.actor+0x24000
        record=struct.pack('<I4xQH6x',symbol_hash('PDA'),array,1)
        ctypes.memmove(jobtable+3*24,record,len(record))
        ctypes.c_uint64.from_address(array).value=obj
        ctypes.c_uint64.from_address(obj).value=self.base+0xc46bb8
        ctypes.c_uint32.from_address(obj+12).value=symbol_hash('acquired')
        ctypes.c_uint32.from_address(obj+16).value=int(acquired)
        self.acquired=obj+16
    def call_fields(self):
        changed=ctypes.c_uint32();result=self.fields(self.base,self.actor,ctypes.byref(changed))
        return result,changed.value
    def test_garage_pad_requires_cop_discovery_and_does_not_unlock_other_fields(self):
        self.prepare_tutorial_fields(discovered=False)
        self.assertEqual(self.call_fields(),(0,0))
        self.assertEqual(ctypes.c_uint32.from_address(self.pad+0x24c).value,0x10100000)
        ctypes.c_ubyte.from_address(self.bank+227//8).value=1<<(227%8)
        self.assertEqual(self.call_fields(),(0,1))
        self.assertEqual(ctypes.c_uint32.from_address(self.pad+0x24c).value,0x100000)
        self.assertEqual(ctypes.c_uint32.from_address(self.other_pad+0x24c).value,0x110200)
        self.assertEqual(ctypes.c_uint16.from_address(self.pad+0x8a).value,0x1007)
        self.assertEqual(ctypes.c_uint32.from_address(self.pad+0x278).value,0x200)
        self.assertEqual(ctypes.c_ubyte.from_address(self.bank+0x80+227).value,0)
        self.assertEqual(self.call_fields(),(0,0))
    def test_mainframe_pad_waits_for_actual_basement_completion(self):
        self.prepare_tutorial_fields(garage=False,acquired=False)
        self.assertEqual(self.call_fields(),(0,0))
        self.assertEqual(ctypes.c_uint32.from_address(self.pad+0x24c).value,0x10000000)
        ctypes.c_ubyte.from_address(self.acquired).value=1
        self.assertEqual(self.call_fields(),(0,1))
        self.assertEqual(ctypes.c_uint32.from_address(self.pad+0x24c).value,0)
        self.assertEqual(ctypes.c_ubyte.from_address(self.acquired).value,1)
        self.assertEqual(ctypes.c_uint32.from_address(self.job_values['LCPD_LobbyEntered']).value,1)
    def test_same_named_keypad_elsewhere_is_not_modified(self):
        self.prepare_tutorial_fields()
        ctypes.c_float.from_address(self.pad+0x22c).value=20
        self.assertEqual(self.call_fields(),(0,0))
        self.assertEqual(ctypes.c_uint32.from_address(self.pad+0x24c).value,0x10100000)
    def prepare_garage_lesson(self, state='LoopChangeClothesHint'):
        self.prepare_tutorial_fields()
        jobs=self.actor+0x30000;manager=jobs+0x308;array=self.actor+0x31000
        comp=self.actor+0x32000;self.ctx=self.actor+0x33000;sm=self.actor+0x34000
        frames=self.actor+0x35000;first=self.actor+0x36000;last=first+0x100
        root=self.actor+0x37000;current=self.actor+0x38000;self.next_state=current+0x100
        finish=current+0x200
        ctypes.c_uint32.from_address(self.base+0x17f8308).value=76
        for address,value in ((self.owner+0xd0+76*8,jobs),(jobs,self.base+0xc47668),
            (manager,self.base+0xc49038),(manager+0x1a0,array),(array,comp),
            (comp,self.base+0xc490a8),(comp+0x18,manager),(comp+0x38,self.ctx),
            (self.ctx,self.base+0xc49010),(self.ctx+0x18,sm),(sm+0x20,self.owner),
            (self.ctx+0x50,frames),(frames,first),(frames+8,last),(first+8,root),
            (last+8,current),(root+0x20,current),(current+8,self.next_state),
            (self.next_state+8,finish),(self.base+0x1c7a830,sm)):
            ctypes.c_uint64.from_address(address).value=value
        ctypes.c_uint32.from_address(manager+0x1a8).value=1
        ctypes.c_ubyte.from_address(self.ctx+0x59).value=2
        for i,(node,name) in enumerate(((current,state),(self.next_state,'ShowCostumeWheelHint'),
                                        (finish,'ActivateLiftDoors'))):
            text=self.actor+0x39000+i*0x100;raw=name.encode()+b'\0'
            ctypes.memmove(text,raw,len(raw));ctypes.c_uint64.from_address(node+0x40).value=text
            ctypes.c_ubyte.from_address(node+0x3a).value=5
        # Keep the required production signature and record the native goto argument.
        code=bytes.fromhex('48 89 5c 24 08 48 89 74 24 10 4c 89 41 28 c3')
        ctypes.memmove(self.base+0x653b60,code,len(code))
        self.current=current

    def test_garage_outfit_lesson_enters_real_keypad_wait_without_completing_basement(self):
        self.prepare_garage_lesson()
        self.assertEqual(self.call_fields(),(0,2))
        self.assertEqual(ctypes.c_uint64.from_address(self.ctx+0x28).value,self.next_state)
        self.assertEqual(ctypes.c_ubyte.from_address(self.acquired).value,0)
        self.assertEqual(ctypes.c_uint32.from_address(self.pad+0x278).value,0x200)
        self.assertEqual(ctypes.c_ubyte.from_address(self.bank+0x80+227).value,0)
        self.assertEqual(ctypes.c_ubyte.from_address(self.base+0xffdfdc).value,1)
        self.assertEqual(self.call_fields(),(0,0))

    def test_garage_flow_does_not_jump_from_other_states_or_nested_callbacks(self):
        self.prepare_garage_lesson('WaitForWardrobe')
        self.assertEqual(self.call_fields(),(0,1))
        self.assertEqual(ctypes.c_uint64.from_address(self.ctx+0x28).value,0)
        ctypes.c_ubyte.from_address(self.ctx+0x59).value=3
        self.assertEqual(self.call_fields(),(0,0))
        self.assertEqual(ctypes.c_uint64.from_address(self.ctx+0x28).value,0)

    def test_garage_flow_rejects_unknown_native_signature_and_state_cycle(self):
        self.prepare_garage_lesson()
        ctypes.c_ubyte.from_address(self.base+0x653b60).value=0x90
        self.assertEqual(self.call_fields(),(1,1))
        self.assertEqual(ctypes.c_uint64.from_address(self.ctx+0x28).value,0)
        ctypes.c_uint64.from_address(self.current+8).value=self.current
        self.assertEqual(self.call_fields(),(5,0))
    def test_completed_basement_disables_both_early_exit_routes_without_reset(self):
        ctypes.c_ubyte.from_address(self.job_values['acquired']).value=1
        self.assertEqual(self.call(),(16,0))
        self.assertEqual(ctypes.c_uint32.from_address(self.job_values['LCPD_LobbyEntered']).value,1)
        self.prepare_garage()
        self.assertEqual(self.call(),(16,0))
        self.assertEqual(ctypes.c_uint32.from_address(self.job_values['LCPD_LobbyEntered']).value,1)
        self.assertEqual(self.counter.value,0)
    def test_failed_custom_icon_experiment_is_removed_without_touching_outputs(self):
        self.prepare_tutorial_fields()
        ctypes.c_uint32.from_address(self.pad+0x24c).value=0x80100000
        ctypes.c_int16.from_address(self.pad+0x3fa).value=632
        ctypes.c_int16.from_address(self.pad+0x3fc).value=580
        self.assertEqual(self.call_fields(),(0,1))
        self.assertEqual(ctypes.c_uint32.from_address(self.pad+0x24c).value,0x100000)
        self.assertEqual(ctypes.c_int16.from_address(self.pad+0x3fa).value,-1)
        self.assertEqual(ctypes.c_int16.from_address(self.pad+0x3fc).value,-1)
        self.assertEqual(ctypes.c_uint32.from_address(self.pad+0x278).value,0x200)
        self.assertEqual(self.call_fields(),(0,0))
    def prepare_chief_key(self):
        from research_profile import symbol_hash
        self.prepare_garage_lesson()
        ctypes.memmove(self.scene_name,b'Police_Station_Lobby\0',21)
        # Add synchronised to the existing typed PDA row.
        system=ctypes.c_uint64.from_address(self.base+0x17eca08).value
        rows=ctypes.c_uint64.from_address(system+0xe0).value
        ctypes.c_uint16.from_address(rows+3*24+16).value=2
        obj=self.actor+0x25000
        ctypes.c_uint64.from_address(self.actor+0x23000+8).value=obj
        ctypes.c_uint64.from_address(obj).value=self.base+0xc46bb8
        ctypes.c_uint32.from_address(obj+12).value=symbol_hash('synchronised')
        ctypes.c_ubyte.from_address(obj+16).value=1;self.synced=obj+16
        ctypes.c_ubyte.from_address(self.acquired).value=1
        for node,name in ((self.current,'DetectiveHint'),(self.next_state,'WaitForChiefLock'),
                          (self.current+0x200,'ChiefAwakesMinicut')):
            text=ctypes.c_uint64.from_address(node+0x40).value
            raw=name.encode()+b'\0';ctypes.memmove(text,raw,len(raw))
        manager=ctypes.c_uint64.from_address(self.owner+0xd0+76*8).value+0x308
        array=ctypes.c_uint64.from_address(manager+0x1a0).value
        comp=self.actor+0x42000;self.scan_ctx=self.actor+0x43000
        frames=self.actor+0x44000;first=self.actor+0x45000;last=first+0x100
        root=self.actor+0x47000;current=self.actor+0x48000;self.scan_next=current+0x100;finish=current+0x200
        sm=ctypes.c_uint64.from_address(self.ctx+0x18).value
        for address,value in ((array+8,comp),(comp,self.base+0xc490a8),(comp+0x18,manager),
            (comp+0x38,self.scan_ctx),(self.scan_ctx,self.base+0xc49010),(self.scan_ctx+0x18,sm),
            (self.scan_ctx+0x50,frames),(frames,first),(frames+8,last),(first+8,root),
            (last+8,current),(root+0x20,current),(current+8,self.scan_next),(self.scan_next+8,finish)):
            ctypes.c_uint64.from_address(address).value=value
        ctypes.c_uint32.from_address(manager+0x1a8).value=2
        ctypes.c_ubyte.from_address(self.scan_ctx+0x59).value=2
        for i,(node,name) in enumerate(((current,'FirstJunction'),(self.scan_next,'Ended'),(finish,'Key_PickedUp'))):
            text=self.actor+0x4d000+i*0x100;raw=name.encode()+b'\0'
            ctypes.memmove(text,raw,len(raw));ctypes.c_uint64.from_address(node+0x40).value=text
            ctypes.c_ubyte.from_address(node+0x3a).value=5
        self.key=self.actor+0x4b000;self.chief_lock=self.actor+0x4c000
        for idx,m,obj,mvt,ovt,name in ((5,self.actor+0x49000,self.key,0xc2b878,0xd748c8,b'M02_Dspot_key_item'),
            (28,self.actor+0x4a000,self.chief_lock,0xc36198,0xc35a98,b'Story_02_LobbyLock')):
            for address,value in ((self.table+idx*8,m),(m,self.base+mvt),(m+0xe0,obj),
                                  (obj,self.base+ovt),(obj+0x48,m),(obj+0x108,self.base+0xc1ba18)):
                ctypes.c_uint64.from_address(address).value=value
            ctypes.memmove(obj+0x58,name+b'\0',len(name)+1)
        code=bytes.fromhex('48 89 5c 24 08 57 48 83 ec 20 89 51 20 48 83 c4 20 5f 48 8b 5c 24 08 c3')
        ctypes.memmove(self.base+0x77d3e0,code,len(code))
    def call_chief(self):
        changed=ctypes.c_uint32();result=self.chief(self.base,self.actor,ctypes.byref(changed))
        return result,changed.value
    def test_chief_key_activates_existing_item_and_original_story_states_once(self):
        self.prepare_chief_key()
        self.assertEqual(self.call_chief(),(0,1))
        self.assertEqual(ctypes.c_uint32.from_address(self.key+0x128).value,1)
        self.assertEqual(ctypes.c_uint64.from_address(self.ctx+0x28).value,self.next_state)
        self.assertEqual(ctypes.c_uint64.from_address(self.scan_ctx+0x28).value,self.scan_next)
        self.assertEqual(ctypes.c_uint32.from_address(self.chief_lock+0x128).value,0)
        self.assertEqual(self.call_chief(),(0,0))
    def test_chief_key_rejects_before_sync_and_away_from_door(self):
        self.prepare_chief_key()
        ctypes.c_ubyte.from_address(self.synced).value=0
        self.assertEqual(self.call_chief(),(0,0))
        ctypes.c_ubyte.from_address(self.synced).value=1
        ctypes.c_float.from_address(self.actor+0x1f0).value=10
        self.assertEqual(self.call_chief(),(0,0))
        self.assertEqual(ctypes.c_uint64.from_address(self.ctx+0x28).value,0)
        self.assertEqual(ctypes.c_uint32.from_address(self.key+0x128).value,0)
    def test_chief_key_validates_both_script_plans_and_native_function_before_activation(self):
        self.prepare_chief_key()
        ctypes.c_ubyte.from_address(self.scan_next+0x3b).value=1
        self.assertEqual(self.call_chief(),(5,0))
        ctypes.c_ubyte.from_address(self.scan_next+0x3b).value=0
        ctypes.c_ubyte.from_address(self.base+0x77d3e0).value=0x90
        self.assertEqual(self.call_chief(),(1,0))
        self.assertEqual(ctypes.c_uint32.from_address(self.key+0x128).value,0)
    def prepare_chief_radio(self):
        self.prepare_chief_key()
        text=ctypes.c_uint64.from_address(self.current+0x40).value
        raw=b'WaitForRadioBuildit\0';ctypes.memmove(text,raw,len(raw))
        manager=self.actor+0x4e000;self.radio_build=self.actor+0x4f000
        for address,value in ((self.table+3*8,manager),(manager,self.base+0xd769c8),
            (manager+0xe0,self.radio_build),(self.radio_build,self.base+0xd76478),
            (self.radio_build+0x48,manager),(self.radio_build+0x108,self.base+0xc1ba18)):
            ctypes.c_uint64.from_address(address).value=value
        ctypes.memmove(self.radio_build+0x58,b'RadioBuildit\0',13)
        ctypes.c_uint16.from_address(self.radio_build+0x8a).value=0x1000
        code=bytes.fromhex('48 89 5c 24 08 57 48 83 ec 20 66 83 49 82 03 48 83 c4 20 5f 48 8b 5c 24 08 c3')
        ctypes.memmove(self.base+0x77d3e0,code,len(code))
    def call_radio(self):
        changed=ctypes.c_uint32();result=self.radio(self.base,self.actor,ctypes.byref(changed))
        return result,changed.value
    def test_chief_radio_reveals_parts_once_without_building_or_advancing_story(self):
        self.prepare_chief_radio()
        self.assertEqual(self.call_radio(),(0,1))
        self.assertEqual(ctypes.c_uint16.from_address(self.radio_build+0x8a).value,0x1003)
        self.assertEqual(ctypes.c_uint64.from_address(self.ctx+0x28).value,0)
        self.assertEqual(ctypes.c_uint32.from_address(self.radio_build+0x128).value,0)
        self.assertEqual(self.call_radio(),(0,0))
    def test_chief_radio_rejects_wrong_story_state_and_distant_actor(self):
        self.prepare_chief_radio()
        ctypes.c_float.from_address(self.actor+0x1f0).value=10
        self.assertEqual(self.call_radio(),(0,0))
        ctypes.c_float.from_address(self.actor+0x1f0).value=0
        text=ctypes.c_uint64.from_address(self.current+0x40).value
        ctypes.memmove(text,b'DetectiveHint\0',14)
        self.assertEqual(self.call_radio(),(0,0))
        self.assertEqual(ctypes.c_uint16.from_address(self.radio_build+0x8a).value,0x1000)
    def test_local_currency_can_add_remove_and_reject_underflow_without_receipt_marker(self):
        from research_profile import symbol_hash
        profile=self.actor+0x50000;stats=self.actor+0x70000
        ctypes.c_uint64.from_address(self.base+0x1c7f160).value=profile
        ctypes.c_uint64.from_address(self.base+0x1c7a830).value=stats
        wallet=ctypes.c_uint64.from_address(profile+0xfb10);wallet.value=5000
        self.assertEqual(self.local_currency(self.base,1000,symbol_hash('TEST_REMOVE_STUDS')),0)
        self.assertEqual(wallet.value,4000)
        self.assertEqual(self.local_currency(self.base,100000,symbol_hash('TEST_REMOVE_STUDS')),12)
        self.assertEqual(wallet.value,4000)
        self.assertEqual(self.local_currency(self.base,10000,symbol_hash('TEST_ADD_STUDS')),0)
        self.assertEqual(wallet.value,14000)
        self.assertEqual(self.local_currency(self.base,1,symbol_hash('TEST_ADD_STUDS')),9)
        self.assertEqual(ctypes.string_at(profile+0x122e0+0x80+1002,22),bytes(22))
    def test_local_model_remove_preserves_real_found_bits_and_rejects_equipped_model(self):
        from research_profile import symbol_hash
        manager=self.actor+0x50000;table=self.actor+0x51000;record=self.actor+0x54000
        bank=self.actor+0x55000;controller=self.actor+0x58000;model=self.actor+0x59000;text=self.actor+0x5a000
        for address,value in ((self.base+0x17ebd38,manager),(manager+0x118,table),(table+227*8,record),
            (record+0x30,text),(self.base+0x1c7cbb8,bank),(self.base+0x17ebe20,controller),(self.actor+0x650,model)):
            ctypes.c_uint64.from_address(address).value=value
        ctypes.c_uint32.from_address(manager+0xe0).value=1002
        ctypes.memmove(text,b'COP\0',4);ctypes.c_int16.from_address(model+8).value=227
        owned=ctypes.c_ubyte.from_address(bank+0x80+227);owned.value=1
        self.assertEqual(self.local_remove(self.base,self.actor,1,227,symbol_hash('COP')),19)
        self.assertEqual(owned.value,1)
        ctypes.c_int16.from_address(model+8).value=244
        for i in range(16):ctypes.c_int16.from_address(controller+0x16a+i*2).value=-1
        ctypes.c_int16.from_address(controller+0x16a).value=227
        self.assertEqual(self.local_remove(self.base,self.actor,1,227,symbol_hash('COP')),0)
        self.assertEqual(owned.value,0)
        self.assertEqual(ctypes.c_ubyte.from_address(bank+227//8).value,0)
        self.assertEqual(ctypes.c_int16.from_address(controller+0x16a).value,-1)
