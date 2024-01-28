byte putdigit(byte digit)
{
    digit;
    asm "mov a, ci";
    asm "cal :printhex4";
    return 0;
}

byte putb(byte value)
{
    value;
    asm "mov a, ci";
    asm "cal :printhex8";
    return 0;
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

byte puts(word Pstr)
{
    //result of this expression is value of Pstr in csci registers
    Pstr;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "cal :printstr";
    return 0;
}

byte readsn(word Pbuf, byte maxlen)
{
    Pbuf;
    asm "psh cs";
    asm "psh ci";
    maxlen;
    asm "pop di";
    asm "pop ds";
    asm "cal :readstr";
    return 0;
}

byte putdecw(word value)
{
    byte digit;
    word divisor;

    divisor <- 10000;

    while(divisor) {
        digit <- value / divisor;
        value <- value - digit * divisor;

        if(digit + (divisor = 1)) {
            putdigit(digit);
        }

        divisor <- divisor / 10;
    }

    return 0;
}