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

byte putsnl(word Pstr)
{
    //result of this expression is value of Pstr in csci registers
    Pstr;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "cal :printstr";
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

    size+4;
    asm "cal :mseek";
    asm "psh cs";
    asm "psh ci";
    asm "psh ds";
    asm "psh di";

    //side effect csci has PlastFree value but dsdi has PlastFree address + 1
    PfirstFree;
    asm "cal :dec16";
    asm "pop ci";
    asm "pop cs";
    asm "cal :poke16";
    PlastNode;
    asm "cal :dec16";
    asm "pop ci";
    asm "pop cs";
    asm "cal :poke16";

    puts("size: ");
    putwnl(size);
    puts("PfirstFree: ");
    putwnl(PfirstFree);
    puts("PlastNode: ");
    putwnl(PlastNode);

    if(PfirstFree = PlastNode) {
        putsnl("A");
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

        PfirstFree + size;
        asm "mov ds, cs";
        asm "mov di, ci";
        asm "mov cs, 0x00";
        asm "mov ci, cs";
        asm "cal :poke16";
    } 
    else 
    {
        word PcurrNodeLen;
        PcurrNodeLen <- #PlastNode;

        if (PcurrNodeLen) 
        {
            putsnl("B");
            word PnewNodeAddr;
            PnewNodeAddr <- PlastNode + 4 + PcurrNodeLen;

            PlastNode + 2;
            asm "psh cs";
            asm "psh ci";
            PnewNodeAddr;
            asm "pop di";
            asm "pop ds";
            asm "cal :poke16";

            PnewNodeAddr;
            asm "psh cs";
            asm "psh ci";
            size;
            asm "pop di";
            asm "pop ds";
            asm "cal :poke16";

            asm "cal :inc16";
            asm "psh ds";
            asm "psh di";
            PfirstFree;
            asm "pop di";
            asm "pop ds";
            asm "cal :poke16";

            PfirstFree <- PnewNodeAddr + 4;
        }
        else
        {
            putsnl("C");
            PlastNode;
            asm "psh cs";
            asm "psh ci";
            size;
            asm "pop di";
            asm "pop ds";
            asm "cal :poke16";

            asm "cal :inc16";
            asm "psh ds";
            asm "psh di";
            PfirstFree;
            asm "pop di";
            asm "pop ds";
            asm "cal :poke16";

            PfirstFree <- PlastNode + 4;
        }
    }

    return PfirstFree;
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

byte mgc()
{
    
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
    word Pvar1;
    word Pvar2;
    word Pvar3;
    word Pvar4;

    Pvar1 <- malloc(4);
    Pvar2 <- malloc(8);
    Pvar3 <- malloc(16);
    Pvar4 <- malloc(32);

    mfill(Pvar1, 4, 0x11);
    mfill(Pvar2, 8, 0x22);
    mfill(Pvar3, 16, 0x33);
    mfill(Pvar4, 32, 0x44);

    putsnl("res1:");
    putwnl(Pvar1);
    putwnl(Pvar2);
    putwnl(Pvar3);
    putwnl(Pvar4);

    mfree(Pvar2);
    mfree(Pvar3);

    Pvar2 <- malloc(8);
    mfill(Pvar2, 32, 0x55);

    putsnl("res2:");
    putwnl(Pvar2);
}
