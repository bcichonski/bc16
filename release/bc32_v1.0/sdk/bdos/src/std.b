#define TRUE 0x01
#define FALSE 0x00

byte peek8(word Paddr)
{
    Paddr;
    asm "mov a, #csci";
    asm "mov cs, 0x00";
    asm "mov ci, a";
}

byte peek16(word Paddr)
{
    Paddr;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "cal :peek16";
}

byte poke8(word Paddr, byte value) 
{
    value;
    asm "mov a, ci";
    asm "psh a";
    Paddr;
    asm "pop a";
    asm "mov #csci, a";
}

byte poke16(word Paddr, word value) 
{
    Paddr;
    asm "psh cs";
    asm "psh ci";
    value;
    asm "pop di";
    asm "pop ds";
    asm "cal :poke16";
}

word parsedecw(word Pbuf, byte maxlen)
{
    word value;
    byte digit;

    value <- 0;

    while (maxlen) {
        digit <- peek8(Pbuf);

        if(!digit) {
          maxlen <- 1;
        }

        if(digit) {
          digit <- digit - '0';
          value <- value * 10 + digit;
        }

        Pbuf <- Pbuf + 1;
        maxlen <- maxlen - 1;
    }

    return value;
}

word mfill(word Paddr, word length, byte value)
{
    Paddr;
    asm "psh cs";
    asm "psh ci";
    value;
    asm "psh a";
    length;
    asm "pop a";
    asm "pop di";
    asm "pop ds";

    asm "cal :mfill";
}

word mzero(word Paddr, word length)
{
    mfill(Paddr, length, 0);
}

word memcpy(word Psource, word Pdesc, word len)
{
    len;
    asm "psh cs";
    asm "psh ci";
    Psource;
    asm "psh cs";
    asm "psh ci";
    Pdesc;
    asm "pop di";
    asm "pop ds";
    asm "pop f";
    asm "pop a";
    asm "cal :mem_cpy";
}