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
        ctypes.c_uint32.from_address(system+0xe8).value=3
        jobs=[('Flow_Setup',[('Flow_Act',1,False)]),
              ('Flow_Setup.Act_1',[('Act1_Mission',1,False),('Act1_Stage',2,False)]),
              ('Flow_Setup.Act_1.LCPD.LCPD_Level.LCPD_Lobby',
               [('LCPD_LobbyEntered',1,False),('LCPD_MainframeActive',0,True)])]
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
        for opcode in (*range(1,11),12,13):
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
