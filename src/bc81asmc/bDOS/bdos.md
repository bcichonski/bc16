# key assumptions
- has to be written in asm unfortunately
- as thin as possible subroutines library for basic operations
- reuse bcOS subroutines where possible
- disk format that supports:
  - files with extensions 8 characters for file + 3 for extension
  - catalogues in form of tree

## disk format
track, sector - kind - description
0, 0 - boot sector - 128 bytes that is a boot loader for the bDOS system
0, 1-?? - bdos itelf - that would give 1920 bytes for the system, it might not be enough
1, 0-15 - bdos cs, another 2048 bytes
2, 0 - disk catalog table
3, 0 - disk catalog table 2
4, 0 - fnode table
5, 0 - fnode table 2
6, 0 - data

## disk catalog table
max length = 16 sectors of 2 track

### single catalog entry
max 255 files / directories per disk
max file size 64kb
catalog entry size: 16bytes = 8 per sector
if there is max 255 files/dirs it can take 32 sectors = two full tracks

00 - 00 entry number 1bytes
01 - 01 parent entry number 1bytes
02 - 03 file size 2bytes
04 - 0c file/dir name 8char
0d - 0f file/dir extension 3char

### single fnode entry
single fnode can have max 16 sectors size (full track)
so max file of size 64kb can have 32 fnodes, but it can have more
fnode size: 8bytes = 16 per sector
full track will contain 256 inodes
00 - 01 fnode number
02 - 03 next fnode number
04 - 04 entry number
05 - 06 start track/sector
07 - 07 length in number of sectors