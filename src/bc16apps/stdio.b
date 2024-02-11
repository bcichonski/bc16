byte putdigit(byte digit)
{
    digit;
    asm "mov a, ci";
    asm "cal :printhex4";
}

byte putb(byte value)
{
    value;
    asm "mov a, ci";
    asm "cal :printhex8";
}

byte putw(word value)
{
    value;
    asm "cal :printhex16";
}

byte putnl()
{
    asm "cal :print_newline";
}

byte puts(word Pstr)
{
    //result of this expression is value of Pstr in csci registers
    Pstr;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "cal :printstr";
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
}

byte putdecw(word value)
{
    byte digit;
    word divisor;
    byte nonzero;

    divisor <- 10000;
    nonzero <- 0;

    while(divisor) {
        digit <- value / divisor;
        value <- value - digit * divisor;

        if(digit + (divisor = 1)) {
            nonzero <- 1;
        }

        if(nonzero) {
            putdigit(digit);
        }
        
        divisor <- divisor / 10;
    }
}