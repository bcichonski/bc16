byte peek8(word Paddr)
{
    Paddr;
    asm "mov a, #csci";
    asm "mov cs, 0x00";
    asm "mov ci, a";
}

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

word malloc(word size)
{
    //allocates new chunk of given size if possible
    //returns pointer to that chunk(+4 from start of chunk to point straight to data)
    //can return 0 which means it is impossible to allocate of given size
    word PlastNode;
    word PfirstFree;

    size;
    asm "cal :mseek";
    asm "psh cs";
    asm "psh ci";
    asm "psh ds";
    asm "psh di";

    //side effect csci has PlastFree value but dsdi has PlastFree address + 1
    PlastNode;
    asm "cal :dec16";
    asm "pop ci";
    asm "pop cs";
    asm "cal :poke16";
    PfirstFree;
    asm "cal :dec16";
    asm "pop ci";
    asm "pop cs";
    asm "cal :poke16";

    puts("PfirstFree: ");
    putwnl(PfirstFree);
    puts("PlastNode: ");
    putwnl(PlastNode);

    if(PfirstFree = PlastNode) {
        puts("case a");
        putnl();
        PfirstFree - 4;
        asm "psh cs";
        asm "psh ci";
        size;
        asm "pop di";
        asm "pop ds";
        asm "cal :poke16";
        asm "cal :inc16";
        asm "psh ds";
        asm "psh di";
        PfirstFree + size;
        asm "pop di";
        asm "pop ds";
        asm "cal :poke16";
    }

    if(!(PfirstFree = PlastNode)) {
        puts("case b");
        putnl();
        PlastNode - 2;
        asm "psh cs";
        asm "psh ci";
        PfirstFree;
        asm "pop di";
        asm "pop ds";
        asm "cal :poke16";
        
        PfirstFree;
        asm "psh cs";
        asm "psh ci";
        size;
        asm "pop di";
        asm "pop ds";
        asm "cal :poke16";

        asm "cal :inc16";
        asm "psh ds";
        asm "psh di";
        PfirstFree + size;
        asm "pop di";
        asm "pop ds";
        asm "cal :poke16";
    }

    return PfirstFree;
}

byte mfree(word Phandle)
{
    //frees chunk of given pointer
    Phandle - 4;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "mov cs, 0x00";
    asm "mov ci, 0x00";
    asm "cal :poke16";

    return 0;
}

byte main()
{
    word Pbuf;
    word Pbuf2;
    word Pbuf3;
    Pbuf <- malloc(16);
    puts("malloc(16): ");
    putwnl(Pbuf);

    Pbuf2 <- malloc(32);
    puts("malloc(32): ");
    putwnl(Pbuf2);

    puts("mfree");
    putnl();
    mfree(Pbuf);

    Pbuf <- malloc(8);
    puts("malloc(8): ");
    putwnl(Pbuf);
}
