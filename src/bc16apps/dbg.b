byte putwnl(word value)
{
    value;
    asm "cal :printhex16";
    asm "cal :print_newline";
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

byte main()
{
    word a;
    word b;

    a <- 3;
    b <- 2;

    if(a < b && b > a) 
    {
        puts("a < b");
    } 
    else if(a = b || a = b + 1)
    {
        puts("a = b");
    }
    else
    {
        puts("a > b");
    }

    putnl();
}
