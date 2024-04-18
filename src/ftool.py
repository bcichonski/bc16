from sys import argv
from bc32 import bc32_env

env = bc32_env.Environment()

def btap2bin(finname,foutname):
    finHandle = env.open_file_to_read(finname)
    foutHandle = env.open_file_to_write(foutname)

    i = 0
    byte = 0
    while True:
        b = env.read_byte(finHandle)
        if not b:
            break

        if ord(b) > 0:
            byte += 2**i
        i += 1
        if i > 7:
            env.write_byte(foutHandle, byte)
            #env.log("write '{0}'".format(byte))
            i = 0
            byte = 0

    env.close_file(finHandle)
    env.close_file(foutHandle)

def checkargs(no):
    lenargv=len(argv)-1
    if lenargv < no:
        env.log("not enough arguments, {} found where it should be at least {}".format(lenargv, no))
        exit(1)

def main():
    env.log("ftool v1.0")

    checkargs(1)
    command=argv[1]

    if command=="btap2bin":
        checkargs(2)
        btap2bin(argv[2]+'.btap',argv[2]+'.bin')
    else:
        env.log('Unknown command: {}'.format(command))

    env.log('Done')

main()