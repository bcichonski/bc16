word strnextword(word Pstring) 
{
    //returns pointer to the next word in string, or _STRNULL if not found
    Pstring;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "cal :nextword";
    asm "jmr nz,:strnnextw";
    asm "mov ds, 0x00";
    asm "mov di, 0x00";
    asm "strnnextw: mov cs, ds";
    asm "mov ci, di";
}

byte strnlen8(word Pstring, byte maxLength) 
{
    Pstring;
    asm "psh cs";
    asm "psh ci";
    maxLength;
    asm "mov cs, ci";
    asm "pop di";
    asm "pop ds";
    asm "cal :str_len8";
    asm "mov cs, 0x00";
}

byte strcpy(word Pstring, word Ptarget)
{
    Pstring;
    asm "psh cs";
    asm "psh ci";
    Ptarget;
    asm "pop di";
    asm "pop ds";
    asm "cal :str_cpy";
}