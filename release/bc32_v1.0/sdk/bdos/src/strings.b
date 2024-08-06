#define NULLCHAR 0x00
#define STRCMP_GT 0xf0
#define STRCMP_LT 0x0f
#define STRCMP_EQ 0x00
#define STRPOS_NOTFOUND 0xffff

byte strpeek8(word Paddr)
{
    Paddr;
    asm "mov a, #csci";
    asm "mov cs, 0x00";
    asm "mov ci, a";
}

byte strpoke8(word Paddr, byte value) 
{
    value;
    asm "mov a, ci";
    asm "psh a";
    Paddr;
    asm "pop a";
    asm "mov #csci, a";
}

word strnextword(word Pstring) 
{
    //returns pointer to the next word in string, or NULLCHAR if not found
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

byte strncpy(word Pstring, word Ptarget, byte len)
{
    Pstring;
    asm "psh cs";
    asm "psh ci";
    len;
    asm "psh ci";
    Ptarget;
    asm "pop a";
    asm "pop di";
    asm "pop ds";
    asm "cal :strncpy";
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
    char1 <- strpeek8(Pstring1);
    char2 <- strpeek8(Pstring2);
    loop <- (char1 != NULLCHAR) && (char2 != NULLCHAR) && (maxlen > 0);

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

        char1 <- strpeek8(Pstring1);
        char2 <- strpeek8(Pstring2);
        
        loop <- (result = 0) && (char1 != NULLCHAR) && (char2 != NULLCHAR) && (i < maxlen);
    }

    if((result = 0) && (i < maxlen))
    {
        if(char1 != NULLCHAR)
        {
            result <- STRCMP_GT;
        }
        else 
        {
            if(char2 != NULLCHAR)
            {
                result <- STRCMP_LT;
            }
        }
    }

    return result;
}

word strnposc(word Pstring, byte char, word maxlen)
{
    word i;
    byte loop;
    byte strchar;
    byte found;

    i <- 0;
    loop <- TRUE;
    found <- FALSE;

    while(loop && (i < maxlen))
    {
        strchar <- strpeek8(Pstring);

        if(strchar = char) 
        {
            loop <- FALSE;
            found <- TRUE;
        }
        else
        {
            if(strchar = NULLCHAR)
            {
                loop <- FALSE;
                found <- FALSE;
            }
        }

        i <- i + 1;
        Pstring <- Pstring + 1;
    }

    if (found)
    {
        i <- i - 1;
    }
    else
    {
        i <- STRPOS_NOTFOUND;
    }

    return i;
}

byte upchar(byte char)
{
    char;
    asm "mov a, ci";
    asm "cal :upchar";
    asm "mov cs, 0x00";
    asm "mov ci, a";
}

byte upstring(word Pstring)
{
    byte strchar;
    byte reschar;
    
    strchar <- strpeek8(Pstring);
    while (strchar != NULLCHAR)
    {
        reschar <- upchar(strchar);
        if(reschar != strchar)
        {
            strpoke8(Pstring, reschar);
        }

        Pstring <- Pstring + 1;
        strchar <- strpeek8(Pstring);
    }
}

word strnextword(word Pstring)
{
    Pstring;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "cal :nextword";
    asm "mov cs, ds";
    asm "mov ci, di";
}
