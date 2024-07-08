#define BDIO_FBINOPENR 0x10
#define BDIO_FBINREAD 0x12

#define BCOSMETA_BDOSCALLADDR 0x007e
#define BCOSMETA_BDOSCALLNO 57

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