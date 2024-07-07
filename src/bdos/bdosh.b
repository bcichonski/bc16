#define BDIO_CALL_ADDRESS 0x388f
#define BDIO_FBINOPENR 0x10

word bdio_call(byte subCode, word param1, word param2)
{
    asm ".def bdio_call, BDIO_CALL_ADDRESS";
    subCode;
    asm "psh ci";
    param2;
    asm "psh ci";
    asm "psh cs";
    param1;
    asm "pop ds";
    asm "pop di";
    asm "pop a";
    asm "cal :bdio_call";
}