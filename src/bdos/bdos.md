# version 1.1 (for bc64 and bc8183 cpu)
# version 1.0
## key assumptions
- is written in b
- as thin as possible subroutines library for basic operations
- reuse bcOS subroutines where possible
- disk format that supports:
  - files with extensions 8 characters for file + 3 for extension
  - flat structure
  - files in continous block

### disk format
The system disc layout and its requirements (boot sector, catalog, BDOS.SYS, where the data starts) are
stated in `src/disc.bddmanifest`. `ftool mkdisc` builds the disc from it and checks them. `ls -a` shows the
actual positions and lengths.

### disk catalog table
max length = 31 sectors (track 0 sector 1 to the end of track 1)

#### single catalog entry
max 248 entries per disk (31 sectors * 8)
max file size 255 sectors = 32640 bytes (length is a single byte)
catalog entry size: 16bytes = 8 per sector

00 - 00 entry number 1bytes
01 - 02 start track and sector
03 - 03 length in sectors
04 - 04 attributes!
05 - 0c file/dir name 8char
0d - 0f file/dir extension 3char

## bdos io
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

## bdio
call numbers as dispatched by bdio_call (see bdioh.b and bdosh.b wrappers)
### low level unbuffered disk io
0x00: bdio_readsect(track, sector, Pmembuf) - read sector and write it to memory
0x01: bdio_writesect(track, sector, Pmembuf) - write sector from memory
0x02: bdio_setdrive(drive, silent) - selects active drive, rereads catalog unless silent
0x03: bdio_getdrive() - return number of active drive
### high level file io
0x10: bdio_fbinopenr(Pfnameext, mode) - opens a file handle associated with given cnameext for read, mode can be raw or buffered
0x11: bdio_fbinopenw(Pfnameext, mode) - opens a file handle for write (this is append only), mode can be raw or buffered
0x12: bdio_fbinread(fhandle, Pmembuf, sectors) - reads given sectors of file to Pmembuf CS=fhandle, CI=sectors, DSDI = Pmembuf
0x13: bdio_fbinwrite(fhandle, Pmembuf, sectors) - writes given memory to sectors
0x14: bdio_fcreate(Pfnameext, attrib) - creates new file with given attribs
0x15: bdio_fclose(fhandle) - closes opened file handle
0x16: bdio_fdelete(Pfnameext) - removes file from disk
0x17: bdio_fsetattr(Pfnameext, attrib) - sets file attributes
### buffered file io (bdos 1.1)
0x18: bdio_fbinbufread(fhandle, Pmembuf, bytes) - reads given number of bytes, length passed via BDIO_VAR_PMEMBUF_LEN (0x0d92)
0x19: bdio_fbinbufwrite(fhandle, Pmembuf, bytes) - writes given number of bytes, length passed via BDIO_VAR_PMEMBUF_LEN (0x0d92)
### random numbers (opt-in, bdos 1.1)
0x1a: BDIO_RANDOM, wrapper random(max) in random.b (include after bdosh.b) - random word from port 0x05; max=0 returns the whole word, else word % max
buffered I/O contract (return values, EOF, flush, buffer counter): see docs/05-bdos.md, section "Buffered I/O"
### internal, used by the shell only (not available via bdio_call)
bdio_ffindfile(Pfnameext) - find a sector in which catalog entry for given name and extension is located
bdio_getfreesect() - returns next free sector to allocate
bdio_execute(Pfnameext) - loads and executes given executable file
bdio_freemem() - returns how much free memory we have
bcos 0x37 (os_metatab entry at 0x007a): bdio_call() - allows to call every bdio subroutine from user program - injected into os_call bcos mechanism
  F = 0x37, A = call number, CSCI = param1, DSDI = param2, then cal :os_metacall

## memory map (bc64, bcos 1.2, bdos 1.1)
0x0000..0x0d6b - bcos 1.2
  0x0008         - os_metacall
  0x000c..0x007b - os_metatab
0x0d80..0x0dd1 - bdio variables and file descriptor tables
0x0dd2..0x0dfe - shell command prompt buffer (programs read their arguments from here)
0x0e00..0x0e7f - bdos boot sector at boot, later temporary sector buffer
0x0e80..0x0eff - catalog scan sector buffer
0x0f00..0x5721 - bdos 1.1 shell + bdio, followed by its variable stack
0x5d00..0x5eff - buffers for buffered file io (128 bytes per handle)
0x5fd0..0x5fff - bdos heap and temporary file name buffer
0x6000..[ST]   - user mem (programs are loaded and called here)
[ST]..0xfffe   - cpu stack

## problems
bdos uses a lot of memory (0x0d80..0x6000), file catalog and user memory start have to move when it grows

## roadmap
1. extending catalog to have file creation dates
2. relocable executables and memory management
3. script execution
4. pipeline io between programs