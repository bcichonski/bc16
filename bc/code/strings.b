byte puts(word Pstr)
{
    //result of this expression is value of Pstr in csci registers
    Pstr;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "cal :printstr";
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

byte main()
{
    puts("hello world");
    putnl();
    putb(255);
    putnl();
    putw(45723);
    return 0;
}