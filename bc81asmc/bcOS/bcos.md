# os features
commandline supports up to 31 characters at single input
commands:
dump <addr> <len> - dumps hex content of memory from <addr> for <len> bytes
print <addr>       - prints content of memory from <addr> as characters, finishes on 0x00
write <addr>       - writes memory from <addr> as chars in 30-chars lines (prints start address of every line)
xwrite <addr>      - writes memory from <addr> as hex in 16-bytes lines
save <addr> <len> <fname> - saves content of memory from <addr> for <len> to tape (as file with preamble, and ending block) performs basic consistency checks
load <addr>       - loads file from tape to memory, <addr> is optional, prints and perform basic checks
help              - prints help
quit              - quits the os
run <addr>       - runs code from <addr> as CAL (program should end in RET)

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
0xfx - system exploded
    0xf0 - user quits the system
    0xff - unexpected system exception - should not happen

# tape file
preamble
00FF00FF00FF00FF
BC05addrlengchks
00filename.ext00
data block