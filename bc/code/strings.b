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
    //putw(Pstr);
    Pstr;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "cal :printstr";
    return 0;
}

byte main()
{
    puts("hello world");
    putnl();
    putb(0xff);
    putnl();
    putw(0xabcd);
    return 0;
}