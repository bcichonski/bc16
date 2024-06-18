#define STRCMP_GT 0xf0
#define STRCMP_LT 0x0f
#define STRCMP_EQ 0x00

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

byte strncmp(word Pstring1, word Pstring2, word maxlen)
{
    byte result;
    byte char1;
    byte char2;
    byte loop;
    word i;

    result <- STRCMP_EQ;
    i <- 0;
    char1 <- #(Pstring1);
    char2 <- #(Pstring2);
    loop <- (char1 != 0) && (char2 != 0) && (maxlen > 0);

    while(loop)
    {
        if(char1 > char2)
        {
            result <- STRCMP_GT;
        }
        else
        {
            if(char1 < char2)
            {
                result <- STRCMP_LT;
            }
        }

        i <- i + 1;
        Pstring1 <- Pstring1 + 1;
        Pstring2 <- Pstring2 + 1;

        char1 <- #(Pstring1);
        char2 <- #(Pstring2);
        loop <- (result = 0) && (char1 != 0) && (char2 != 0) && (i < maxlen);
    }

    if((result = 0) && (i < maxlen))
    {
        if(char1 != 0)
        {
            result <- STRCMP_GT;
        }
        else 
        {
            if(char2 != 0)
            {
                result <- STRCMP_LT;
            }
        }
    }

    return result;
}