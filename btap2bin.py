#!/usr/bin/python3

from bc16 import bc16_env
from sys import argv

env = bc16_env.Environment()
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
    if not b:
        break

    if ord(b) > 0:
        byte += i**2
    i += 1
    if i > 7:
        env.write_byte(foutHandle, byte)
        i = 0
        byte = 0

env.close_file(finHandle)
env.close_file(foutHandle)

env.log('Done')
