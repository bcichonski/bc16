byte peek8(word Paddr)
{
    Paddr;
    asm "mov a, #csci";
    asm "mov cs, 0x00";
    asm "mov ci, a";
}

byte putw(word value)
{
    value;
    asm "cal :printhex16";
    return 0;
}

byte putnl()
{
    asm "cal :print_newline";
    return 0;
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

byte main()
{
    word Pbuf;
    word val;
    Pbuf <- "123";
    putw(Pbuf);
    putnl();
    val <- parsedecw(Pbuf, 6);
    putw(val);
    putnl();
    putw(Pbuf);
    putnl();
}
