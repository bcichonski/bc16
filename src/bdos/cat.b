#code 0x6000
#heap 0xa000

#include std.b
#include bdosh.b
#include strings.b
#include bdostools.b
#include bdosargs.b

#define MODE_CHAR 0x10
#define MODE_BIN 0x20
#define MODE_HELP 0x40
#define INFILEBDIONAME_ADDR 0xa020
#define INFILEBUF_ADDR 0xa100
#define BINPERLINE 0x20
#define CHARPERLINE 0x50
#define CHAR_PRINTABLE_MIN 0x20
#define CHAR_PRINTABLE_MAX 0x7e
#define CHAR_LF 0x13

word printchars(word Pstart, word len, word linelen)
{
    byte char;
    word curr;
    curr <- len;

    while(curr)
    {
        char <- peek8(Pstart);

        if((char >= CHAR_PRINTABLE_MIN) && (char <= CHAR_PRINTABLE_MAX))
        {
            if((linelen + 1) > CHARPERLINE)
            {
                putsnl(" !catln1");
                linelen <- 0;
            }

            linelen <- linelen + 1;
            putc(char);
        }
        else
        {
            if(char = CHAR_LF)
            {
                putsnl(" !ln");
                linelen <- 0;
            }
            else 
            {
                if((linelen + 3) > CHARPERLINE)
                {
                    putsnl(" !catln2");
                    linelen <- 0;
                }
                linelen <- linelen + 3;
                printf("#%x", char);
            }
        }

        Pstart <- Pstart + 1;
        curr <- curr - 1;
    }

    return linelen;
}

word printbins(word Pstart, word len, word Preladdr)
{
    word curr;
    curr <- len;

    printf("%w: ", Preladdr);

    while(curr)
    {
        putb(peek8(Pstart));
        puts(" ");

        Pstart <- Pstart + 1;
        curr <- curr - 1;
    }

    putnl();

    return len;
}

word printbuf(word Pmembuf, word Preladdr, byte options, word linelen)
{
    word Plast;
    word Pnext;
    Plast <- Pmembuf + BDIO_SECTBUF_LEN;

    if(options & MODE_CHAR)
    {
        linelen <- printchars(Pmembuf, BDIO_SECTBUF_LEN, linelen);
    }
    else
    {
        while(Pmembuf < Plast)
        {
            Pnext <- printbins(Pmembuf, BINPERLINE, Preladdr);

            Pmembuf <- Pmembuf + Pnext;
            Preladdr <- Preladdr + Pnext;
        }
    }

    return linelen;
}

byte printfile(byte sourcedrive, word Psourcefileext, byte options)
{
    byte currentDrive;
    byte activeDrive;
    byte fHandleIn;
    byte sectorsread;
    word reladdr;
    word linelen;

    printf("printing %s:%s with options %x...%n", getdriveletter(sourcedrive), Psourcefileext, options);

    activeDrive <- bdio_getdrive();
    currentDrive <- changeDriveIfNeeded(activeDrive, sourcedrive, FALSE);

    fHandleIn <- bdio_fbinopenr(Psourcefileext, BDIO_FOPEN_MODE_SECTOR);
    if(fHandleIn < BDIO_FOPEN_FNAME_NOTFOUND)
    {
        reladdr <- 0;
        linelen <- 0;
        sectorsread <- bdio_fbinread(fHandleIn, INFILEBUF_ADDR, 0x01);

        while(sectorsread)
        {
            linelen <- printbuf(INFILEBUF_ADDR, reladdr, options, linelen);
            reladdr <- reladdr + BDIO_SECTBUF_LEN;

            sectorsread <- bdio_fbinread(fHandleIn, INFILEBUF_ADDR, 0x01);
            if((options & MODE_CHAR) = 0)
            {
                putnl();
            }
        }

        bdio_fclose(fHandleIn);
    }
    else
    {
        bdio_printexecres(fHandleIn);
    }

    poke8(BDIO_VAR_ACTIVEDRV, 0xff);//force cat refresh
    bdio_setdrive(activeDrive, FALSE);
}

byte getoptions(word Poptions)
{
    byte result;
    byte option;

    result <- 0;
    option <- getswitch(Poptions, "HBC");

    if(option = 1)
    {
        result <- MODE_HELP;
    }
    else
    {
        if(option = 2)
        {
            result <- MODE_BIN;
        }
        else
        {
            if(option = 3)
            {
                result <- MODE_CHAR;
            }
            else
            {
                putsnl("error: unknown switch");
            }
        }
    }

    return result;
}

byte main()
{
    word Pargs;
    word result;
    byte sourcedrv;
    byte len;
    byte options;

    upstring(BDIO_CMDPROMPTADDR);
    Pargs <- strnextword(BDIO_CMDPROMPTADDR);
    options <- getoptions(Pargs);

    if(options & MODE_HELP)
    {
        printusage("print files",
            "-b binary",
            "-c characters");
    }
    else
    {
        Pargs <- strnextword(Pargs);

        result <- argfile(Pargs, INFILEBDIONAME_ADDR);
        sourcedrv <- result;

        printfile(sourcedrv, INFILEBDIONAME_ADDR, options);
    }

    putnl();
}