#define PRINTF_FORMATCHAR '%'
#define PRINTF_STATE_NORMAL 0x01
#define PRINTF_STATE_FORMAT 0x02
#define PRINTF_STATE_END 0x00

byte putdigit(byte digit)
{
    digit;
    asm "mov a, ci";
    asm "cal :printhex4";
}

byte putb(byte value)
{
    value;
    asm "mov a, ci";
    asm "cal :printhex8";
}

byte putw(word value)
{
    value;
    asm "cal :printhex16";
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
}

byte puts(word Pstr)
{
    //result of this expression is value of Pstr in csci registers
    Pstr;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "cal :printstr";
}

byte putsnl(word Pstr)
{
    //result of this expression is value of Pstr in csci registers
    Pstr;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "cal :printstr";
    asm "cal :print_newline";
}

byte readsn(word Pbuf, byte maxlen)
{
    Pbuf;
    asm "psh cs";
    asm "psh ci";
    maxlen;
    asm "pop di";
    asm "pop ds";
    asm "cal :readstr";
}

byte putdecw(word value)
{
    byte digit;
    word divisor;
    byte nonzero;

    divisor <- 10000;
    nonzero <- 0;

    while(divisor) 
    {
        digit <- value / divisor;
        value <- value - digit * divisor;

        if(digit & (divisor = 1)) 
        {
            nonzero <- 1;
        }

        if(nonzero) {
            putdigit(digit);
        }
        
        divisor <- divisor / 10;
    }
}

byte putdecwnl(word value)
{
    putdecw(value);
    asm "cal :print_newline";
}

byte iopeek8(word Paddr)
{
    Paddr;
    asm "mov a, #csci";
    asm "mov cs, 0x00";
    asm "mov ci, a";
}

byte printf(word PformatStr)***
{
    word PdynParam;
    byte currChar;
    byte state;
    byte params;
    word currParamVal;
    byte handled;

    puts("printf: ");putw(PformatStr);puts(" ");putw(printfPLEN);putnl();

    PformatStr;
    asm "cal :inc16";
    asm "psh ds";
    asm "psh di";
    PdynParam;
    asm "cal :dec16";
    asm "pop ci";
    asm "pop cs";
    asm "cal :poke16";

    state <- PRINTF_STATE_NORMAL;
    params <- 0;

    while(state && (params < printfPLEN))
    {
        currChar <- iopeek8(PformatStr);
        handled <- FALSE;

        putw(PformatStr);puts(" ");putw(PdynParam);puts(" ");
        putb(currChar);putnl();

        if(currChar != 0)
        {
            if(state = PRINTF_STATE_NORMAL)
            {
                if(currChar = PRINTF_FORMATCHAR)
                {
                    state <- PRINTF_STATE_FORMAT;
                    putsnl("format");
                }
                else
                {
                    currChar;
                    asm "mov ds, 0x01";
                    asm "mov a, ci";
                    asm "out #ds, a";
                }
                handled <- TRUE;
            }

            if(!handled) 
            {
                if(currChar = PRINTF_FORMATCHAR)
                {
                    putsnl("fchar");
                    asm "mov ds, 0x01";
                    asm "mov a, 0x25";
                    asm "out #ds, a";
                    handled <- TRUE;
                }
                if(!handled && (currChar = 'n'))
                {
                    putsnl("nl");
                    puts(currParamVal);
                    handled <- TRUE;
                } 
                if(!handled)
                {
                    currParamVal <- #(PdynParam);
                    PdynParam <- PdynParam + 2;
                    params <- params + 1;
                    
                    puts("dyn: ");
                    putwnl(currParamVal);

                    if(currChar = 'd')
                    {
                        putdecw(currParamVal);
                    }
                    if(currChar = 'x')
                    {
                        putb(currParamVal);
                    }
                    if(currChar = 'w')
                    {
                        putw(currParamVal);
                    }
                    if(currChar = 's')
                    {
                        puts(currParamVal);
                    }
                }
                state <- PRINTF_STATE_NORMAL;
            }
        }
        else
        {
            state <- PRINTF_STATE_END;
        }

        PformatStr <- PformatStr + 1;
    }

    return 0;
}
