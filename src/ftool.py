from sys import argv
from bc32 import bc32_env
from bc32 import bc32_io

env = bc32_env.Environment()

def btap2bin(finname,foutname):
    finHandle = env.open_file_to_read(finname)
    foutHandle = env.open_file_to_write(foutname)

    i = 0
    byte = 0
    preamble = 0
    while True:
        b = env.read_byte(finHandle)
        if not b:
            break

        if ord(b) > 0:
            byte += 2**i
        i += 1
        if i > 7:
            preamble += 1
            if preamble > 24:
                env.write_byte(foutHandle, byte)
            i = 0
            byte = 0

    env.close_file(finHandle)
    env.close_file(foutHandle)

def checkargs(no):
    lenargv=len(argv)-1
    if lenargv < no:
        env.log("not enough arguments, {} found where it should be at least {}".format(lenargv, no))
        exit(1)

sectorSize = bc32_io.FloppyDriveV1.SECTOR_SIZE
sectors = bc32_io.FloppyDriveV1.SECTORS
tracks = bc32_io.FloppyDriveV1.TRACKS

def createbdd(fname):
    size = sectorSize * sectors * tracks

    fhandle = env.open_file_to_write(fname)

    i=0
    while(i<size):
        env.write_byte(fhandle, 0x00)
        i+=1

    env.close_file(fhandle)

def dumpsector(fname, track, sector):
    env.log('file {} track {} sector {}'.format(fname, track, sector))
    fhandle = env.open_file_to_read(fname)
    position = (track*sectors + sector)*sectorSize
    env.move_file_handle(fhandle, position)
    buf = env.read_bytes(fhandle, sectorSize)
    env.close_file(fhandle)

    i = 0
    line = ''
    for val in buf:
        line += '{0:02x} '.format(val)
        i += 1
        if i == 16:
            env.log(line)
            line = ''
            i = 0

    if i != 0:
        env.log(line)

def main():
    env.log("ftool v1.0")

    checkargs(1)
    command=argv[1]

    if command=="btap2bin":
        checkargs(2)
        btap2bin(argv[2]+'.btap',argv[2]+'.bin')
    elif command=='createbdd':
        checkargs(2)
        createbdd(argv[2]+'.bdd')
    elif command=='dumpsector':
        checkargs(4)
        dumpsector(argv[2]+'.bdd', int(argv[3]), int(argv[4]))
    else:
        env.log('Unknown command: {}'.format(command))

    env.log('Done')

main()