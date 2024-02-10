//heap begins at value stored in SYS_HEAPHEAD (usually 0x3000)
//it consists memory chunks wrapped in records
//each chunk is a node of a linked list, by offset:
//0x0000: chunk length
//0x0002: next chunk address
//0x0004: data(of requested length)

#define NULL 0x0000

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

    if(PfirstFree = PlastNode) {
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

    if(!(PfirstFree = PlastNode)) 
    {
        word PcurrNodeLen;
        PcurrNodeLen <- #PfirstFree;

        if (PcurrNodeLen) 
        {
            word PnewNodeAddr;
            PnewNodeAddr <- PfirstFree + 4 + PcurrNodeLen;

            PfirstFree + 2;
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
            PlastNode;
            asm "pop di";
            asm "pop ds";
            asm "cal :poke16";

            PfirstFree <- PnewNodeAddr + 4;
        }

        if (!PcurrNodeLen) {
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
            PlastNode;
            asm "pop di";
            asm "pop ds";
            asm "cal :poke16";
        }
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

word mhead()
{
    asm ".mv dsdi, :sys_heaphead";
    asm "cal :peek16";
}

word mtotal()
{
    word Pcurr;
    word Plast;

    Pcurr <- mhead();
    Plast <- Pcurr;
    
    while(Pcurr) {
        Plast <- Pcurr;
        Pcurr <- #(Pcurr + 2);
    }

    Pcurr;
    asm "cal :dec16";
    asm "mov cs, ss";
    asm "mov ci, si";
    asm "cal :poke16";

    Pcurr <- Pcurr - Plast;

    return Pcurr;
}
