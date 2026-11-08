import contextlib
import io
import os
import shutil
import tempfile
import unittest
from bc64 import bc64_env
from bc64 import bc64_io
from bc64 import bc64_mem

FDD = bc64_io.FloppyDriveV1
TR = bc64_io.TapeRecorder


class ScriptedEnvironment(bc64_env.Environment):
    """Real file helpers, silent, with prompts answered from a queue (never reads stdin)."""

    def __init__(self, answers=()):
        super().__init__(False)
        self.answers = list(answers)
        self.prompts = []

    def get_string(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0)


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bc64dev")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def path(self, name):
        return os.path.join(self.tmp, name)


class FloppyDriveTests(TempDirTestCase):
    SECTOR_BYTES = FDD.SECTOR_SIZE
    DISK_SIZE = FDD.TRACKS * FDD.SECTORS * FDD.SECTOR_SIZE

    def create_fdd(self, answers=("diska",)):
        env = ScriptedEnvironment([self.path(a) for a in answers])
        mem = bc64_mem.MemBus(env, 0x1000)
        fdd = FDD(env, mem)
        self.addCleanup(self.close_handles, fdd)
        return fdd, env, mem

    @staticmethod
    def close_handles(fdd):
        for handle in (fdd.fileA_handle, fdd.fileB_handle):
            if handle is not None and not handle.closed:
                handle.close()

    @staticmethod
    def send(fdd, *data):
        for b in data:
            fdd.write_byte(b)

    def configure_dma(self, fdd, addr):
        self.send(fdd, FDD.CMD_CFG, addr >> 8, addr & 0xff)

    def read_sector(self, fdd, track, sector):
        self.send(fdd, FDD.CMD_READSECT, track, sector)

    def write_sector(self, fdd, track, sector):
        self.send(fdd, FDD.CMD_WRITESECT, track, sector)

    def sector_offset(self, track, sector):
        return (track * FDD.SECTORS + sector) * FDD.SECTOR_SIZE

    def fill(self, mem, addr, pattern):
        for i in range(FDD.SECTOR_SIZE):
            mem.write_byte(addr + i, (pattern + i) & 0xff)

    def test_geometry_constants(self):
        self.assertEqual(self.DISK_SIZE, 131072)

    def test_initial_state_is_ready(self):
        fdd, env, mem = self.create_fdd()
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY)
        self.assertEqual(fdd.io_port, 0x08)
        self.assertEqual(fdd.active_drive, 'A')

    def test_ping_reports_fdd_v1(self):
        fdd, env, mem = self.create_fdd()
        self.send(fdd, FDD.CMD_PING)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY | FDD.STATE_FDDV1)

    def test_dma_address_configuration(self):
        fdd, env, mem = self.create_fdd()
        self.send(fdd, FDD.CMD_CFG)
        self.assertEqual(fdd.read_byte(), FDD.STATE_CFG1)
        self.send(fdd, 0x12)
        self.assertEqual(fdd.read_byte(), FDD.STATE_CFG2)
        self.send(fdd, 0x34)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY)
        self.assertEqual(fdd.dmaaddr, 0x1234)

    def test_dma_address_with_high_byte_equal_to_ping_command_is_misread(self):
        # pinned (D7 finding): PING is matched before the CFG1 state, so a DMA high byte of 0xf0
        # is taken as a ping and the address is never configured.
        fdd, env, mem = self.create_fdd()
        self.send(fdd, FDD.CMD_CFG, FDD.CMD_PING)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY | FDD.STATE_FDDV1)
        self.assertIsNone(fdd.dmaaddr)

    def test_drive_select(self):
        fdd, env, mem = self.create_fdd()
        self.send(fdd, FDD.CMD_SETDRVB)
        self.assertEqual(fdd.active_drive, 'B')
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY)
        self.send(fdd, FDD.CMD_SETDRVA)
        self.assertEqual(fdd.active_drive, 'A')
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY)

    def test_command_sequence_states(self):
        fdd, env, mem = self.create_fdd()
        self.configure_dma(fdd, 0x100)
        self.send(fdd, FDD.CMD_READSECT)
        self.assertEqual(fdd.read_byte(), FDD.STATE_RD1)
        self.send(fdd, 0)
        self.assertEqual(fdd.read_byte(), FDD.STATE_RD2)
        self.send(fdd, 0)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY)
        self.send(fdd, FDD.CMD_WRITESECT)
        self.assertEqual(fdd.read_byte(), FDD.STATE_WR1)
        self.send(fdd, 0)
        self.assertEqual(fdd.read_byte(), FDD.STATE_WR2)
        self.send(fdd, 0)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY)

    def test_disk_is_created_on_first_access_and_named_with_bdd_extension(self):
        fdd, env, mem = self.create_fdd()
        name = self.path("diska.bdd")
        self.assertFalse(os.path.exists(name))
        self.configure_dma(fdd, 0x100)
        self.read_sector(fdd, 0, 0)
        self.assertTrue(os.path.exists(name))
        self.assertEqual(os.path.getsize(name), self.DISK_SIZE)
        with open(name, "rb") as f:
            self.assertEqual(f.read(), bytes(self.DISK_SIZE))
        self.assertEqual(env.prompts, ["Disk A name:"])
        self.assertEqual(fdd.fileA_name, name)

    def test_name_with_bdd_extension_is_kept(self):
        fdd, env, mem = self.create_fdd(("disk.bdd",))
        self.configure_dma(fdd, 0x100)
        self.read_sector(fdd, 0, 0)
        self.assertTrue(os.path.exists(self.path("disk.bdd")))
        self.assertFalse(os.path.exists(self.path("disk.bdd.bdd")))

    def test_existing_disk_is_not_recreated_and_prompt_asked_once(self):
        name = self.path("diska.bdd")
        with open(name, "wb") as f:
            f.write(bytes([0x55]) * self.DISK_SIZE)
        fdd, env, mem = self.create_fdd()
        self.configure_dma(fdd, 0x100)
        self.read_sector(fdd, 1, 1)
        self.read_sector(fdd, 2, 2)
        self.assertEqual(env.prompts, ["Disk A name:"])
        self.assertEqual(mem.read_byte(0x100), 0x55)
        self.assertEqual(mem.read_byte(0x100 + FDD.SECTOR_SIZE - 1), 0x55)
        with open(name, "rb") as f:
            self.assertEqual(f.read(), bytes([0x55]) * self.DISK_SIZE)

    def test_read_loads_exactly_one_sector_at_dma_address(self):
        name = self.path("diska.bdd")
        image = bytearray(self.DISK_SIZE)
        offset = self.sector_offset(3, 5)
        image[offset:offset + FDD.SECTOR_SIZE] = bytes((i + 1) & 0xff for i in range(FDD.SECTOR_SIZE))
        with open(name, "wb") as f:
            f.write(image)
        fdd, env, mem = self.create_fdd()
        self.configure_dma(fdd, 0x200)
        self.read_sector(fdd, 3, 5)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY)
        self.assertEqual(bytes(mem.mem[0x200:0x200 + FDD.SECTOR_SIZE]),
                         bytes((i + 1) & 0xff for i in range(FDD.SECTOR_SIZE)))
        self.assertEqual(mem.read_byte(0x1ff), 0)
        self.assertEqual(mem.read_byte(0x200 + FDD.SECTOR_SIZE), 0)

    def test_write_then_read_round_trip(self):
        fdd, env, mem = self.create_fdd()
        self.fill(mem, 0x300, 0x10)
        expected = bytes(mem.mem[0x300:0x300 + FDD.SECTOR_SIZE])
        self.configure_dma(fdd, 0x300)
        self.write_sector(fdd, 7, 9)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY)
        for i in range(FDD.SECTOR_SIZE):
            mem.write_byte(0x300 + i, 0)
        self.configure_dma(fdd, 0x400)
        self.read_sector(fdd, 7, 9)
        self.assertEqual(bytes(mem.mem[0x400:0x400 + FDD.SECTOR_SIZE]), expected)

    def test_write_touches_only_its_own_sector_in_the_file(self):
        fdd, env, mem = self.create_fdd()
        self.fill(mem, 0x300, 0x80)
        self.configure_dma(fdd, 0x300)
        self.write_sector(fdd, 2, 3)
        fdd.fileA_handle.flush()
        with open(self.path("diska.bdd"), "rb") as f:
            image = f.read()
        self.assertEqual(len(image), self.DISK_SIZE)
        offset = self.sector_offset(2, 3)
        self.assertEqual(image[offset:offset + FDD.SECTOR_SIZE], bytes(mem.mem[0x300:0x300 + FDD.SECTOR_SIZE]))
        self.assertEqual(image[:offset], bytes(offset))
        self.assertEqual(image[offset + FDD.SECTOR_SIZE:], bytes(self.DISK_SIZE - offset - FDD.SECTOR_SIZE))

    def test_last_track_and_sector_are_accessible(self):
        fdd, env, mem = self.create_fdd()
        self.fill(mem, 0x300, 0x01)
        self.configure_dma(fdd, 0x300)
        self.write_sector(fdd, FDD.TRACKS - 1, FDD.SECTORS - 1)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY)
        fdd.fileA_handle.flush()
        with open(self.path("diska.bdd"), "rb") as f:
            image = f.read()
        self.assertEqual(len(image), self.DISK_SIZE)
        self.assertEqual(image[-FDD.SECTOR_SIZE:], bytes(mem.mem[0x300:0x300 + FDD.SECTOR_SIZE]))

    def test_drives_a_and_b_use_separate_disks(self):
        fdd, env, mem = self.create_fdd(("diska", "diskb"))
        self.fill(mem, 0x300, 0x20)
        self.configure_dma(fdd, 0x300)
        self.write_sector(fdd, 0, 0)
        self.send(fdd, FDD.CMD_SETDRVB)
        self.configure_dma(fdd, 0x400)
        self.read_sector(fdd, 0, 0)
        self.assertEqual(env.prompts, ["Disk A name:", "Disk B name:"])
        self.assertEqual(bytes(mem.mem[0x400:0x400 + FDD.SECTOR_SIZE]), bytes(FDD.SECTOR_SIZE))
        self.assertEqual(fdd.fileB_name, self.path("diskb.bdd"))
        self.assertNotEqual(fdd.fileA_handle, fdd.fileB_handle)

    def test_read_with_track_out_of_range_fails(self):
        fdd, env, mem = self.create_fdd()
        self.configure_dma(fdd, 0x100)
        self.read_sector(fdd, FDD.TRACKS, 0)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READ_FAILURE)
        self.assertEqual(env.prompts, [])  # failure is detected before any disk is asked for
        self.assertFalse(os.path.exists(self.path("diska.bdd")))

    def test_read_with_sector_out_of_range_fails(self):
        fdd, env, mem = self.create_fdd()
        self.configure_dma(fdd, 0x100)
        self.read_sector(fdd, 0, FDD.SECTORS)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READ_FAILURE)

    def test_write_with_out_of_range_track_reports_read_failure(self):
        # pinned (D7 finding): check() always reports STATE_READ_FAILURE; STATE_WRITE_FAILURE is never used
        fdd, env, mem = self.create_fdd()
        self.configure_dma(fdd, 0x100)
        self.write_sector(fdd, 0xff, 0)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READ_FAILURE)
        self.assertNotEqual(fdd.read_byte(), FDD.STATE_WRITE_FAILURE)

    def test_write_with_out_of_range_sector_reports_read_failure(self):
        fdd, env, mem = self.create_fdd()
        self.configure_dma(fdd, 0x100)
        self.write_sector(fdd, 0, 0xff)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READ_FAILURE)

    def test_ping_recovers_from_failure(self):
        fdd, env, mem = self.create_fdd()
        self.read_sector(fdd, FDD.TRACKS, 0)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READ_FAILURE)
        self.send(fdd, FDD.CMD_PING)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY | FDD.STATE_FDDV1)

    def test_commands_are_ignored_while_in_failure_state(self):
        # pinned: a read command is only accepted in STATE_READY
        fdd, env, mem = self.create_fdd()
        self.read_sector(fdd, FDD.TRACKS, 0)
        self.send(fdd, FDD.CMD_READSECT)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READ_FAILURE)

    def test_write_without_active_drive_is_a_drive_failure(self):
        fdd, env, mem = self.create_fdd()
        fdd.active_drive = None
        self.configure_dma(fdd, 0x100)
        self.write_sector(fdd, 0, 0)
        self.assertEqual(fdd.read_byte(), FDD.STATE_DRIVE_FAILURE)

    def test_read_without_active_drive_stays_in_command_state(self):
        # pinned (D7 finding): unlike write, read has no drive-failure branch, and the fall-through
        # assigns the typo'd attribute "setate" (see FDD unknown command), so the state never changes.
        fdd, env, mem = self.create_fdd()
        fdd.active_drive = None
        self.configure_dma(fdd, 0x100)
        self.read_sector(fdd, 0, 0)
        self.assertEqual(fdd.read_byte(), FDD.STATE_RD2)

    def test_eject_without_active_drive_is_a_drive_failure(self):
        fdd, env, mem = self.create_fdd()
        fdd.active_drive = None
        self.send(fdd, FDD.CMD_EJECT)
        self.assertEqual(fdd.read_byte(), FDD.STATE_DRIVE_FAILURE)

    def test_eject_with_unknown_drive_is_a_drive_failure(self):
        fdd, env, mem = self.create_fdd()
        fdd.active_drive = 'C'
        self.send(fdd, FDD.CMD_EJECT)
        self.assertEqual(fdd.read_byte(), FDD.STATE_DRIVE_FAILURE)

    def test_eject_closes_disk_and_next_access_prompts_again(self):
        fdd, env, mem = self.create_fdd(("diska", "diskc"))
        self.configure_dma(fdd, 0x100)
        self.read_sector(fdd, 0, 0)
        handle = fdd.fileA_handle
        self.send(fdd, FDD.CMD_EJECT)
        self.assertTrue(handle.closed)
        self.assertIsNone(fdd.fileA_handle)
        self.assertIsNone(fdd.fileA_name)
        self.read_sector(fdd, 0, 0)
        self.assertEqual(len(env.prompts), 2)
        self.assertEqual(fdd.fileA_name, self.path("diskc.bdd"))

    def test_eject_only_affects_the_active_drive(self):
        fdd, env, mem = self.create_fdd(("diska", "diskb"))
        self.configure_dma(fdd, 0x100)
        self.read_sector(fdd, 0, 0)
        self.send(fdd, FDD.CMD_SETDRVB)
        self.read_sector(fdd, 0, 0)
        handle_a = fdd.fileA_handle
        self.send(fdd, FDD.CMD_EJECT)
        self.assertIsNone(fdd.fileB_handle)
        self.assertIs(fdd.fileA_handle, handle_a)
        self.assertFalse(handle_a.closed)

    def test_eject_without_disk_is_a_no_op(self):
        fdd, env, mem = self.create_fdd()
        self.send(fdd, FDD.CMD_EJECT)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY)
        self.assertIsNone(fdd.fileA_handle)

    def test_create_disk_writes_zeroed_image(self):
        fdd, env, mem = self.create_fdd()
        fdd.create_disk(self.path("new.bdd"))
        with open(self.path("new.bdd"), "rb") as f:
            self.assertEqual(f.read(), bytes(self.DISK_SIZE))

    def test_short_write_raises_disk_write_error(self):
        # pinned: the host-level failure surfaces as a plain Exception
        fdd, env, mem = self.create_fdd()
        self.configure_dma(fdd, 0x100)
        env.write_bytes = lambda handle, data: 0
        opened = []
        real_open = env.open_file_to_readwrite
        env.open_file_to_readwrite = lambda name: opened.append(real_open(name)) or opened[-1]
        self.addCleanup(lambda: [h.close() for h in opened])
        with self.assertRaises(Exception) as ctx:
            self.write_sector(fdd, 0, 0)
        self.assertEqual(str(ctx.exception), "Disk write error")

    @unittest.expectedFailure
    def test_unknown_command_sets_drive_failure_state(self):
        # #4 item 4: the code assigns "self.setate", so the state does not change
        fdd, env, mem = self.create_fdd()
        self.send(fdd, 0x99)
        self.assertEqual(fdd.read_byte(), FDD.STATE_DRIVE_FAILURE)

    def test_unknown_command_leaves_state_unchanged_today(self):
        # pinned today's behaviour, owned by #4
        fdd, env, mem = self.create_fdd()
        self.send(fdd, 0x99)
        self.assertEqual(fdd.read_byte(), FDD.STATE_READY)
        self.assertEqual(fdd.setate, FDD.STATE_DRIVE_FAILURE)


class TapeRecorderTests(TempDirTestCase):
    def create_tape(self, answers=("tape",)):
        env = ScriptedEnvironment([self.path(a) for a in answers])
        tape = TR(env)
        self.addCleanup(self.close_handle, tape)
        return tape, env

    @staticmethod
    def close_handle(tape):
        handle = getattr(tape, "file_handle", None)
        if handle is not None and not handle.closed:
            handle.close()

    def make_tape_file(self, name, bits):
        with open(self.path(name + ".btap"), "wb") as f:
            f.write(bytes(bits))

    def test_initial_state_is_ready(self):
        tape, env = self.create_tape()
        self.assertEqual(tape.io_port, 0x02)
        self.assertTrue(tape.read_byte() & TR.READY)
        self.assertFalse(tape.read_byte() & (TR.TAPE4READ | TR.TAPE4WRITE | TR.MOVE | TR.ERROR))

    def test_commands_without_tx_are_ignored(self):
        tape, env = self.create_tape()
        tape.write_byte(TR.TAPE4READ)
        self.assertEqual(tape.intstate, TR.READY)
        self.assertEqual(env.prompts, [])

    def test_tape4read_prompts_for_name_and_opens_file(self):
        self.make_tape_file("tape", [1, 0])
        tape, env = self.create_tape()
        tape.write_byte(TR.TAPE4READ | TR.TX)
        self.assertEqual(env.prompts, ["Type name of the tape to read: "])
        self.assertEqual(tape.intstate, TR.TAPE4READ)
        state = tape.read_byte()
        self.assertTrue(state & TR.READY)
        self.assertTrue(state & TR.TAPE4READ)
        self.assertFalse(state & TR.ERROR)

    def test_tape4read_of_missing_file_sets_error(self):
        tape, env = self.create_tape(("nothere",))
        tape.write_byte(TR.TAPE4READ | TR.TX)
        self.assertEqual(tape.intstate, TR.ERROR)
        self.assertTrue(tape.read_byte() & TR.ERROR)

    def test_move_before_a_tape_is_loaded_sets_error(self):
        tape, env = self.create_tape()
        tape.write_byte(TR.MOVE | TR.TX)
        state = tape.read_byte()
        self.assertTrue(state & TR.ERROR)
        self.assertFalse(state & TR.MOVE)
        self.assertFalse(state & TR.READY)

    def test_tape4read_while_moving_sets_error(self):
        self.make_tape_file("tape", [1])
        tape, env = self.create_tape()
        tape.write_byte(TR.TAPE4READ | TR.TX)
        tape.write_byte(TR.MOVE | TR.TX)
        tape.write_byte(TR.TAPE4READ | TR.TX)
        self.assertTrue(tape.state.get() & TR.ERROR)

    def test_read_path_state_transitions(self):
        self.make_tape_file("tape", [1, 0, 1])
        tape, env = self.create_tape()
        tape.write_byte(TR.TAPE4READ | TR.TX)
        self.assertEqual(tape.intstate, TR.TAPE4READ)
        tape.write_byte(TR.MOVE | TR.TX)
        self.assertEqual(tape.intstate, TR.MOVE)
        state = tape.state.get()
        self.assertTrue(state & TR.MOVE)
        self.assertTrue(state & TR.TAPE4READ)
        self.assertFalse(state & TR.READY)
        handle = tape.file_handle
        tape.write_byte(TR.READY | TR.TX)
        self.assertEqual(tape.intstate, TR.READY)
        self.assertTrue(handle.closed)
        self.assertIsNone(tape.file_handle)
        state = tape.read_byte()
        self.assertTrue(state & TR.READY)
        self.assertFalse(state & (TR.MOVE | TR.TAPE4READ))

    def test_moving_tape_delivers_one_bit_per_status_read(self):
        self.make_tape_file("tape", [1, 0, 129, 0])
        tape, env = self.create_tape()
        tape.write_byte(TR.TAPE4READ | TR.TX)
        tape.write_byte(TR.MOVE | TR.TX)
        bits = []
        for _ in range(4):
            state = tape.read_byte()
            self.assertTrue(state & TR.TX)
            bits.append(int(bool(state & TR.DX)))
        self.assertEqual(bits, [1, 0, 1, 0])

    def test_read_bit_handshake_without_move(self):
        self.make_tape_file("tape", [1, 0])
        tape, env = self.create_tape()
        tape.write_byte(TR.TAPE4READ | TR.TX)
        tape.write_byte(TR.TX)  # request a bit
        self.assertTrue(tape.state.get_flag(TR.F_DX))
        self.assertFalse(tape.state.get_flag(TR.F_TX))
        tape.write_byte(TR.TX)
        self.assertFalse(tape.state.get_flag(TR.F_DX))

    def test_end_of_tape_raises_type_error_today(self):
        # pinned (D7 finding): at end of file env.read_byte returns b"" and ord(b"") raises TypeError;
        # there is no end-of-tape status, the exception reaches the CPU run loop.
        self.make_tape_file("tape", [1])
        tape, env = self.create_tape()
        tape.write_byte(TR.TAPE4READ | TR.TX)
        tape.write_byte(TR.MOVE | TR.TX)
        tape.read_byte()
        with self.assertRaises(TypeError):
            tape.read_byte()

    def test_end_of_tape_in_bit_handshake_raises_type_error_today(self):
        # pinned (D7 finding), same cause as above
        self.make_tape_file("tape", [1])
        tape, env = self.create_tape()
        tape.write_byte(TR.TAPE4READ | TR.TX)
        tape.write_byte(TR.TX)
        with self.assertRaises(TypeError):
            tape.write_byte(TR.TX)

    def test_write_path_creates_tape_file(self):
        tape, env = self.create_tape(("out",))
        tape.write_byte(TR.TAPE4WRITE | TR.TX)
        self.assertEqual(env.prompts, ["Type name of the tape to write: "])
        tape.write_byte(TR.MOVE | TR.TX)
        for bit in (1, 0, 1, 1):
            tape.write_byte(bit | TR.TX)
        tape.write_byte(TR.READY | TR.TX)
        with open(self.path("out.btap"), "rb") as f:
            self.assertEqual(f.read(), bytes([1, 0, 1, 1]))

    def test_tape4write_into_unwritable_location_sets_error(self):
        env = ScriptedEnvironment([os.path.join(self.tmp, "no_such_dir", "t")])
        tape = TR(env)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):  # production code prints the error text
            tape.write_byte(TR.TAPE4WRITE | TR.TX)
        self.assertIn("no_such_dir", out.getvalue())
        self.assertEqual(tape.intstate, TR.ERROR)
        self.assertTrue(tape.read_byte() & TR.ERROR)


if __name__ == "__main__":
    unittest.main()
