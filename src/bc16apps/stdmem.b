word malloc(word size)
{
    return size;
}

byte free(word Phandle, word size)
{
    return 0;
}

byte peek8(word Paddr)
{
    Paddr;
    asm "mov a, #csci";
    asm "mov cs, 0x00";
    asm "mov ci, a";
}

byte peek16(word Paddr)
{
    Paddr;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "cal :peek16";
}

byte poke8(word Paddr, byte value) 
{
    value;
    asm "mov a, ci";
    Paddr;
    asm "mov #csci, a";
}

byte poke16(word Paddr, word value) 
{
    Paddr;
    asm "psh cs";
    asm "psh ci";
    value;
    asm "pop di";
    asm "pop ds";
    asm "cal :poke16";
}