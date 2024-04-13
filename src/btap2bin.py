#!/usr/bin/python3

from bc32 import bc32_env
from sys import argv

env = bc32_env.Environment()
if len(argv) < 2:
    env.log('Need two args fin.btap and fout.bin')
    exit(1)

fin = argv[1] + '.btap'
fout = argv[2] + '.bin'

env.log('Converting {0} to {1}'.format(fin, fout))

finHandle = env.open_file_to_read(fin)
foutHandle = env.open_file_to_write(fout)

i = 0
byte = 0
while True:
    b = env.read_byte(finHandle)
    #env.log("read '{0}'".format(b))

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

env.log('Done')
