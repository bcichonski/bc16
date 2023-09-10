byte peek8(word Paddr)
{
    Paddr;
    asm "mov a, #csci";
    asm "mov cs, 0x00";
    asm "mov ci, a";
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
        asm "kil";
    }

    return value;
}

byte main()
{
    word Pbuf;
    Pbuf <- "0123";
    
    parsew(Pbuf, 4);
}
