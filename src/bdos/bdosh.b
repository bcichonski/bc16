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

byte bdio_fbinopenr(word Pfnameext)
{
    return bdio_call(BDIO_FBINOPENR, Pfnameext, 0x0000);
}

byte bdio_fbinread(byte fhandle, word Pmembuf, byte sectors)
{
    return bdio_call(BDIO_FBINREAD, (fhandle << 8) | sectors, Pmembuf);
}

byte bdio_fclose(byte fhandle)
{
    return bdio_call(BDIO_FCLOSE, fhandle, 0x0000);
}