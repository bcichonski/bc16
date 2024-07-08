# key assumptions
- is written in b
- as thin as possible subroutines library for basic operations
- reuse bcOS subroutines where possible
- disk format that supports:
  - files with extensions 8 characters for file + 3 for extension
  - flat structure
  - files in continous block

## disk format
track, sector - kind - description
0, 0 - boot sector - 128 bytes that is a boot loader for the bDOS system
0, 1 - bdos itself - that would give 1848 bytes for the system, it might not be enough
1-7, 0-15 - bdos cs, another 2048 bytes * 5
8, 0 - disk catalog table
9, 0 - disk catalog table 2
10, 0 - data

## disk catalog table
max length = 16 sectors of 2 track

### single catalog entry
max 255 files per disk
max file size 64kb
catalog entry size: 16bytes = 8 per sector
if there is max 255 files/dirs it can take 32 sectors = two full tracks

00 - 00 entry number 1bytes
01 - 02 start track and sector
03 - 03 length in sectors
04 - 04 attributes!
05 - 0c file/dir name 8char
0d - 0f file/dir extension 3char

# bdos io
key assumptions
- file can be a representation of a device that can be read from/writen to or both
- file can be a physical file on disk
- files have to cover continous space of disk blocks, if there is not enough blocks error happens
- there are no directories
- there are some limitations in how file system stores meta on files, therefore number of files and their size is limited
- up to 3 files can be open to read at the same time, but only one can be written (continous)
- bdos subroutines are made to be call indirectly, to allow compatibility with further versions of system
- bdos subroutines are called bdio and offers basic functions, they are loaded and always present
- bdos then has an internal program called shell that uses bdio to:
  - keep track on ACTIVE DRIVE within that drive (for both drives)
  - is able to locate the executive program file of given name, load it to memory and execute it
  - it can also pass command line arguments to that program
  - to make shell as simple as possible all system command including: FORMAT, PWD, LS, CP, MV and others are executives
- files have attributes:
  - R=0x01 if allowed to be read
  - W=0x02 if allowed to be modified
  - X=0x04 if allowed to be executed
  - S=0x80 if system(system files attributes cannot be changed)

# bdio
## low level unbuffered disk io
0x00: bdio_readsec(track, sector, Pmembuf) - read sector and write it to memory
0x01: bdio_writesec(track, sector, Pmembuf) - write sector from memory
0x02: bdio_setdrive(drive) - selects active drive
## medium level io
0x03: bdio_getdrive() - return number of active drive
0x04: bdio_ffindfile(Pfnameext) - find a sector in which catalog entry for given name and extension is located
0x05: bdio_getfreesect() - returns next free sector to allocate
## high level unbuffered file io
0x10: bdio_fbinopenr(Pfnameext) - opens a file handle associated with given cnameext for read
0x11: bdio_fbinopenw(Pfnameext) - opens a file handle for write (this is append only)
0x12: bdio_fbinread(fhandle, Pmembuf, sectors) - reads given sectors of file to Pmembuf CS=fhandle, CI=sectors, DSDI = Pmembuf
0x13: bdio_fbinwrite(fhandle, Pmembuf, sectors) - writes given memory to sectors
0x14: bdio_fcreate(Pfnameext) - creates or truncates an existing file
0x15: bdio_fclose(fhandle) - closes opened file handle
0x16: bdio_fdelete(Pfnameext) - removes file from disk
0x17: bdio_fsetattrib(Pfnameext, attrib) - sets file attributes
## high level shell api
0x20: bdio_execute(Pfnameext) - loads and executes given executable file
0x21: bdio_freemem() - returns how much free memory we have
bcos 0x57: bdio_call() - allows to call every bdio subroutine from user program - injected into os_call bcos mechanism

# memory map
0x0000..0x0e45 - bcos 1.1 (real)
  0x0008         - os_metacall
  0x000c..0x0080 - os_metatab
  0x0081..0x0090 - os_vartab
0x0e46..0x0e79 - unused buffer for bcos
0x0e80..0x0eff - bdos boot sector
0x0f00..0x3aff - bdos 1.0 shell
0x3b00..0x3eff - bdos stack
0x3f00..0x4000 - bdos heap
0x4000..[ST]   - user mem
[ST]..0x7fff   - cpu stack

# problems
bdos uses too much memory, its 0f00..4000 already and growing
this means file catalog is moved too 