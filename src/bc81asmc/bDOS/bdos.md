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

# bdos io
key assumptions
- file can be a representation of a device that can be read from/writen to or both
- file can be a physical file on disk
- directory is just for grouping files
- there are some limitations in how file system stores meta on files, therefore number of directories/files and their size is limited
- bdos subroutines are made to be call indirectly, to allow compatibility with further versions of system
- bdos subroutines are called bdio and offers basic functions, they are loaded and always present
- bdos then has an internal program called shell that uses bdio to:
  - keep track on ACTIVE DRIVE and ACTIVE PATH within that drive (for both drives)
  - is able to locate the executive program file of given name, load it to memory and execute it
  - it can also pass command line arguments to that program
  - to make shell as simple as possible all system command including: FORMAT, PWD, LS, CP, MV and others are executives

# bdio
## low level unbuffered disk io
0x00: bdio_rsect(track, sector, memaddr) - read sector and write it to memory
0x01: bdio_wsect(track, sector, memaddr) - write sector from memory
0x02: bdio_cfindsect(cnameext, mamaddr) - find a sector in which catalog entry for given name and extension is located, leave it in memory
0x03: bdio_freesect() - returns next free sector to allocate
0x04: bdio_setdrive(drive) - selects active drive
0x05: bdio_getdrive() - return number of active drive
## high level unbuffered file io
0x10: bdio_fbinopenr(cparent, cnameext) - opens a file handle associated with given cnameext for read
0x11: bdio_fbinopenw(cparent, cnameext) - opens a file handle for write (this is append only)
0x12: bdio_fbinread(fhandle, memaddr, sectors) - reads given sectors of file to memaddr
0x13: bdio_fbinwrite(fhandle, memaddr, sectors) - writes given memory to sectors
0x14: bdio_fcreate(cparent, cnameext) - creates or truncates an existing file
0x15: bdio_fclose(fhandle) - close open file handle
0x16: bdio_fdelete(cparent, cnameext) - removes file from disk
0x17: bdio_dcreate(cparent, cnameext) - creates a new directory
0x18: bdio_ddelete(cparent, cnameext) - removes directory (must be empty)
0x19: bdio_fstat(cparent, cnameext) - return statistics on file
0x1a: bdio_dirstat(cparent, cnameext) - return statistics on directory
0x1b: bdio_dstat() - return statistics on active drive
## high level shell api
0x20: bdos_getenv(name) - returns value of a given environment variable
0x21: bdos_setenv(name, value) - sets value of a given variable
0x22: bdos_execute(cnameext) - loads and executes given executable file

# memory map
0x0000..0x0e45 - bcos 1.1 (real)
  0x0008         - os_metacall
  0x000c..0x0080 - os_metatab
  0x0081..0x0090 - os_vartab
0x0e46..0x0e80 - unused buffer for bcos
0x0e81..0x2000 - bdos 1.0 code
0x2001..0x2f00 - bdos stack
0x2f01..0x3000 - bdos heap
0x3001..[ST]   - user mem
[ST]..0x7fff   - cpu stack