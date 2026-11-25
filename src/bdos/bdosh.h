#define BCOSMETA_BDOSCALLADDR 0x007a
#define BCOSMETA_BDOSCALLNO 55
#define BNULL 0x00

word bdio_call(byte subCode, word param1, word param2)
byte bdio_setdrive(byte drive, byte silent)
byte bdio_getdrive()
byte bdio_fbinopenr(word Pfnameext, byte mode)
byte bdio_fbinopenw(word Pfnameext, byte mode)
byte bdio_fbinread(byte fhandle, word Pmembuf, byte sectors)
byte bdio_fbinwrite(byte fhandle, word Pmembuf, byte sectors)
byte bdio_fclose(byte fhandle)
byte bdio_fcreate(word Pfnameext, byte attribs)
byte bdio_fdelete(word Pfnameext)
byte bdio_fsetattr(word Pfnameext, byte attribs)
byte bdio_readsect(byte track, byte sector, word Pmembuf)
byte bdio_writesect(byte track, byte sector, word Pmembuf)
word bdio_fbinbufread(byte fhandle, word Pmembuf, word bytes)
word bdio_fbinbufwrite(byte fhandle, word Pmembuf, word bytes)
