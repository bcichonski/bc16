#include bdioh.b

#define BCOSMETA_BDOSCALLADDR 0x007e
#define BCOSMETA_BDOSCALLNO 57
#define BNULL 0x00

word bdio_call(byte subCode, word param1, word param2)
{
    BCOSMETA_BDOSCALLNO;
    asm "psh ci";
    subCode;
    asm "psh ci";
    param2;
    asm "psh ci";
    asm "psh cs";
    param1;
    asm "pop ds";
    asm "pop di";
    asm "pop a";
    asm "pop f";
    asm "cal :os_metacall";
}

byte bdio_setdrive(byte drive, byte silent)
{
    return bdio_call(BDIO_SETDRIVE, drive << 8, silent << 8);
}

byte bdio_getdrive()
{
    return bdio_call(BDIO_GETDRIVE, 0x0000, 0x0000);
}

byte bdio_fbinopenr(word Pfnameext)
{
    return bdio_call(BDIO_FBINOPENR, Pfnameext, 0x0000);
}

byte bdio_fbinopenw(word Pfnameext)
{
    return bdio_call(BDIO_FBINOPENW, Pfnameext, 0x0000);
}

byte bdio_fbinread(byte fhandle, word Pmembuf, byte sectors)
{
    return bdio_call(BDIO_FBINREAD, (fhandle << 8) | sectors, Pmembuf);
}

byte bdio_fbinwrite(byte fhandle, word Pmembuf, byte sectors)
{
    return bdio_call(BDIO_FBINWRITE, (fhandle << 8) | sectors, Pmembuf);
}

byte bdio_fclose(byte fhandle)
{
    return bdio_call(BDIO_FCLOSE, fhandle, 0x0000);
}

byte bdio_fcreate(word Pfnameext, byte attribs)
{
    return bdio_call(BDIO_FCREATE, Pfnameext, attribs << 8);
}

byte bdio_fdelete(word Pfnameext)
{
    return bdio_call(BDIO_FDELETE, Pfnameext, 0x0000);
}

byte bdio_fsetattr(word Pfnameext, byte attribs)
{
    return bdio_call(BDIO_FDELETE, Pfnameext, attribs << 8);
}

byte bdio_readsect(byte track, byte sector, word Pmembuf)
{
    return bdio_call(BDIO_READSECTOR, (track << 8) | sector, Pmembuf);
}

byte bdio_writesect(byte track, byte sector, word Pmembuf)
{
    return bdio_call(BDIO_WRITESECTOR, (track << 8) | sector, Pmembuf);
}