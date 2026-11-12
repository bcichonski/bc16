# os v1.2 features
extended library of subroutines
usage of new bc8183 cpu instruction set

# os v1.1 features
extended library of subroutines
additional code at boot to detect floppy drive and load a bootloader for bdos 1.0
small fixes

# os features
commandline supports up to 32 characters at single input
commands are selected by their first letter only, <addr> and <len> are always 4 hex digits:
d <addr> <len>    - dump: dumps hex content of memory from <addr> for <len> bytes (16 bytes per line)
p <addr> <len>    - print: prints content of memory from <addr> for <len> bytes as characters
w <addr>          - write: stores typed lines as chars to memory from <addr>, stops on empty line (prints start address of every line)
x <addr>          - xwrite: stores typed lines as 2-digit hex bytes to memory from <addr>, stops on empty line
s <addr> <len> <fname> - save: saves content of memory from <addr> for <len> to tape (as file with preamble) performs basic consistency checks
l [<addr>]        - load: loads file from tape to memory, <addr> is optional (default is the address stored in the file), prints and perform basic checks
h                 - help: prints help
q                 - quit: quits the os (fatal 0xf0, cpu stops)
r <addr>          - run: runs code from <addr> as CAL (program should end in RET)
e <addr>          - exe: runs code as jump to <addr> (program should end in jumping back to :os_goto_parse, :os_parse or 0x0000
which will reset the OS)

# system calls
programs call bcos subroutines indirectly: function number in F (mov a, NN; psh a; pop f), then cal :os_metacall (0x0008)
the full table of function numbers is in docs/04-bcos.md
entry 0x37 (0x007a) is filled in by bdos with the address of bdio_call

# error codes
0x0x - soft errors
    0x01 - unrecognized command
    0x02 - required argument 1 missing
    0x03 - parse 4 digit hex argument 1 failed
    0x04 - required argument 2 missing
    0x05 - parse 4 digit hex argument 2 failed
    0x06 - parse 2 digit hex failed (xwrite)
    0x07 - required argument 3 missing
0x1x - overflow
    0x10 - overflow in INC16
    0x11 - overflow in DEC16
    0x12 - overflow in ADD16
    0x13 - overflow in SUB16
0xce - compatibility error - current version of os does not have subprocedure that was called
0xex - fdd errors
0xfx - system exploded
    0xf0 - user quits the system
    0xff - unexpected system exception - should not happen

# tape file
preamble
00FF00FF
BC05addr
leng00 f
 i l e n
 a m e .
 e x t00
data block

s 1000 1000 filename.txt