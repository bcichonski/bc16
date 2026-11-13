#code 0x6000
#heap 0xf000

#include std.b
#include stdmem.b
#include bdosh.b

// calc v1.0: a four-function calculator for bdos (CALC.PRG on utils.bdd).
// Numbers are unsigned 16-bit words (1..5 decimal digits, up to 65535); results wrap modulo 65536.
// The input buffer comes from malloc; nothing below 0x6000 is touched.

#define CALCBUFLEN 8

byte print_help()
{
    putsnl("+ for addition");
    putsnl("- for subtraction");
    putsnl("* for multiplication");
    putsnl("/ for division");
    putsnl("h for help");
    putsnl("q for quit");
}

// 1 when the zero-terminated string at Pstr is 1 to 5 digits with a value of at most 65535.
byte checknum(word Pstr)
{
    byte ok;
    byte count;
    byte done;
    byte c;
    byte last;
    word prefix;

    ok <- 1;
    count <- 0;
    done <- 0;
    last <- 0;
    prefix <- 0;

    while(!done)
    {
        c <- peek8(Pstr);
        if(c = 0)
        {
            done <- 1;
        }

        if(!done)
        {
            if((c < '0') || (c > '9'))
            {
                ok <- 0;
                done <- 1;
            }
        }

        if(!done)
        {
            if(count < 4)
            {
                prefix <- (prefix * 10) + (c - '0');
            }
            if(count = 4)
            {
                last <- c - '0';
            }
            count <- count + 1;
            Pstr <- Pstr + 1;
        }
    }

    if(count = 0)
    {
        ok <- 0;
    }
    if(count > 5)
    {
        ok <- 0;
    }
    if(count = 5)
    {
        // 65535 = 6553 followed by 5
        if(!((prefix < 6553) || ((prefix = 6553) && (last < 6))))
        {
            ok <- 0;
        }
    }

    return ok;
}

word parsenum(word Pstr)
{
    word value;
    byte c;

    value <- 0;
    c <- peek8(Pstr);
    while(c)
    {
        value <- (value * 10) + (c - '0');
        Pstr <- Pstr + 1;
        c <- peek8(Pstr);
    }

    return value;
}

byte calc(byte operator, word Pbuf)
{
    word arg1;
    word arg2;
    word res;
    byte ok;

    puts("1>");
    readsn(Pbuf, CALCBUFLEN);
    ok <- checknum(Pbuf);

    if(!ok)
    {
        putsnl("error: bad number");
    }

    if(ok)
    {
        arg1 <- parsenum(Pbuf);

        puts("2>");
        readsn(Pbuf, CALCBUFLEN);
        ok <- checknum(Pbuf);

        if(!ok)
        {
            putsnl("error: bad number");
        }
    }

    if(ok)
    {
        arg2 <- parsenum(Pbuf);

        if((operator = '/') && (arg2 = 0))
        {
            putsnl("error: division by zero");
            ok <- 0;
        }
    }

    if(ok)
    {
        res <- 0;

        if(operator = '+')
        {
            res <- arg1 + arg2;
        }
        if(operator = '-')
        {
            res <- arg1 - arg2;
        }
        if(operator = '*')
        {
            res <- arg1 * arg2;
        }
        if(operator = '/')
        {
            res <- arg1 / arg2;
        }

        puts("res>");
        putdecw(res);
        putnl();
    }
}

byte runcommand(word Pbuf)
{
    byte command;
    byte result;
    byte handled;

    puts("calc>");
    readsn(Pbuf, 2);
    command <- peek8(Pbuf);

    result <- 1;
    handled <- 0;

    if(command = 'h')
    {
        print_help();
        handled <- 1;
    }

    if(command = 'q')
    {
        result <- 0;
        handled <- 1;
    }

    if((command = '+') || (command = '-') || (command = '*') || (command = '/'))
    {
        calc(command, Pbuf);
        handled <- 1;
    }

    if(!handled)
    {
        putsnl("error: unknown command, type h for help");
    }

    return result;
}

byte main()
{
    word Pbuf;
    byte again;

    putsnl("calc v1.0");
    putsnl("type h for help");

    Pbuf <- malloc(CALCBUFLEN);

    again <- 1;
    while(again)
    {
        again <- runcommand(Pbuf);
    }

    mfree(Pbuf);

    putsnl("bye");

    return 0;
}
