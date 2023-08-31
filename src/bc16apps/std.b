
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
    Paddr;
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

word parsew(word Pbuf, byte maxlen)
{
    word value;
    byte digit;
    word Pcurr;

    Pcurr <- Pbuf;
    value <- 0;
    while (maxlen) {
        digit <- peek8(Pcurr);
        digit <- digit - '0';

        value <- value * 10 + digit;

        Pcurr <- Pcurr + 1;
        maxlen <- maxlen - 1;
    }

    return value;
}