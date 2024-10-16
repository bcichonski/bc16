#code 0x5800
#heap 0x7000

#include std.b
#include bdosh.b
#include strings.b

#define MODE_CHAR 0x10
#define MODE_BIN 0x20
#define MODE_HELP 0x40
#define DRIVEPRESENT 0x0100
#define INFILEBDIONAME_ADDR 0x7cf0
#define INFILEBUF_ADDR 0x7d00
#define BINPERLINE 0x20
#define CHARPERLINE 0x40
#define CHAR_PRINTABLE_MIN 0x20
#define CHAR_PRINTABLE_MAX 0x7e

word getdriveletter(byte drive)
{
    word driveLetter;
    driveLetter <- "?";
    if(drive = BDIO_DRIVEA)
    {
        driveLetter <- "A";
    }
    else
    {
        if(drive = BDIO_DRIVEB) 
        {
            driveLetter <- "B";
        }
    }

    return driveLetter;
}

word getdrive(word Pargs)
{
    word result;

    if(strncmp(Pargs, "A:", 2) = STRCMP_EQ)
    {
        result <- BDIO_DRIVEA | DRIVEPRESENT;
    }
    else
    {
        if(strncmp(Pargs, "B:", 2) = STRCMP_EQ)
        {
            result <- BDIO_DRIVEB | DRIVEPRESENT;
        }
        else
        {
            result <- bdio_getdrive();
        }
    }
    return result;
}

byte changeDriveIfNeeded(byte currentDrive, byte targetDrive, byte silent)
{
    if(currentDrive != targetDrive)
    {
        bdio_setdrive(targetDrive, silent);
        currentDrive <- targetDrive;
    }
    return currentDrive;
}

word printchars(word Pstart, word len)
{
    byte char;
    word curr;
    curr <- len;
    byte linelen;

    linelen <- 0;

    while(curr)
    {
        char <- peek8(Pstart);

        if((char >= CHAR_PRINTABLE_MIN) && (char <= CHAR_PRINTABLE_MAX))
        {
            linelen <- linelen + 1;
            if(linelen > CHARPERLINE)
            {
                putnl();
                linelen <- 0;
            }

            putc(char);
        }
        else
        {
            linelen <- linelen + 3;
            if(linelen > CHARPERLINE)
            {
                putnl();
                linelen <- 0;
            }
            printf("#%x", char);
        }

        Pstart <- Pstart + 1;
        curr <- curr - 1;
    }

    return len;
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

byte printbuf(word Pmembuf, word Preladdr, byte options)
{
    word Plast;
    word Pnext;
    Plast <- Pmembuf + BDIO_SECTBUF_LEN;

    while(Pmembuf < Plast)
    {
        if(options & MODE_CHAR)
        {
            Pnext <- printchars(Pmembuf, CHARPERLINE);
        }
        else
        {
            Pnext <- printbins(Pmembuf, BINPERLINE, Preladdr);
        }

        Pmembuf <- Pmembuf + Pnext;
        Preladdr <- Preladdr + Pnext;
    }
}

byte printfile(byte sourcedrive, word Psourcefileext, byte options)
{
    byte currentDrive;
    byte activeDrive;
    byte fHandleIn;
    byte sectorsread;
    word reladdr;

    //printf("printing %s:%s with options %x...%n", getdriveletter(sourcedrive), Psourcefileext, options);

    activeDrive <- bdio_getdrive();
    currentDrive <- changeDriveIfNeeded(activeDrive, sourcedrive, FALSE);

    fHandleIn <- bdio_fbinopenr(Psourcefileext);
    if(fHandleIn < BDIO_FOPEN_FNAME_NOTFOUND)
    {
        reladdr <- 0;
        sectorsread <- bdio_fbinread(fHandleIn, INFILEBUF_ADDR, 0x01);

        while(sectorsread)
        {
            printbuf(INFILEBUF_ADDR, reladdr, options);
            reladdr <- reladdr + BDIO_SECTBUF_LEN;

            sectorsread <- bdio_fbinread(fHandleIn, INFILEBUF_ADDR, 0x01);
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

byte fnormalize(word Pfilenameext, word Pbdiofilename)
{
    byte length;

    mfill(Pbdiofilename, BDIO_FCAT_ENTRY_NAMELEN, 0x20);
    poke8(Pbdiofilename + BDIO_FCAT_ENTRY_NAMELEN, NULLCHAR);

    length <- strnlen8(Pfilenameext, BDIO_FCAT_ENTRY_NAMELEN + 1);
    strncpy(Pfilenameext + length - 3, Pbdiofilename + BDIO_FCAT_ENTRY_NAMELEN - 3, 3);

    length <- strnposc(Pfilenameext, '.', BDIO_FCAT_ENTRY_NAMELEN);
    strncpy(Pfilenameext, Pbdiofilename, length);
}

byte getoptions(word Poptions)
{
    byte result;
    byte val;
    byte bit;

    result <- 0;

    if(strncmp(Poptions, "-H", 2) = STRCMP_EQ)
    {
        result <- MODE_HELP;
    }
    else 
    {
        if(strncmp(Poptions, "-B", 2) = STRCMP_EQ)
        {
            result <- MODE_BIN;
        }
        else
        {
            if(strncmp(Poptions, "-C", 2) = STRCMP_EQ)
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
    word PsrcFileNameExt;
    byte sourcedrv;
    byte len;
    byte options;

    upstring(BDIO_CMDPROMPTADDR);
    Pargs <- strnextword(BDIO_CMDPROMPTADDR);
    options <- getoptions(Pargs);

    if(options & MODE_HELP)
    {
        printf("%s%n%s%n%s%n",
            "print files",
            "-b binary",
            "-c characters");
    }
    else
    {
        Pargs <- strnextword(Pargs);

        result <- getdrive(Pargs);
        poke8(Pargs - 1, NULLCHAR);
        if(result & DRIVEPRESENT)
        {
            Pargs <- Pargs + 2;
        }

        PsrcFileNameExt <- Pargs;
        sourcedrv <- result;

        fnormalize(PsrcFileNameExt, INFILEBDIONAME_ADDR);

        printfile(sourcedrv, INFILEBDIONAME_ADDR, options);
    }
}