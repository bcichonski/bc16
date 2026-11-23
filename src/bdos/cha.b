#code 0x6000
#heap 0xa000

#include std.b
#include bdosh.b
#include strings.b
#include bdostools.b
#include bdosargs.b

#define MODE_SET 0x10
#define MODE_UNSET 0x20
#define MODE_HELP 0x40
#define INFILEBDIONAME_ADDR 0xa7f0

byte changeattributes(byte sourcedrive, word Psourcefileext, byte options)
{
    byte currentDrive;
    byte activeDrive;
    byte fAttribsIn;
    byte fHandleIn;
    byte fAttribsOut;
    word Pfcatentry;
    byte attrmask;

    //printf("changing attributes %s:%s with options %x...%n", getdriveletter(sourcedrive), Psourcefileext, options);

    activeDrive <- bdio_getdrive();
    currentDrive <- changeDriveIfNeeded(activeDrive, sourcedrive, FALSE);

    fHandleIn <- bdio_fbinopenr(Psourcefileext, BDIO_FOPEN_MODE_SECTOR);
    attrmask <- BDIO_FILE_ATTRIB_EXEC | BDIO_FILE_ATTRIB_READ | BDIO_FILE_ATTRIB_SYSTEM | BDIO_FBINWRITE;

    if(fHandleIn < BDIO_FOPEN_FNAME_NOTFOUND)
    {
        Pfcatentry <- #(BDIO_VAR_FCAT_PLASTFOUND);
        fAttribsIn <- peek8(Pfcatentry + BDIO_FCAT_ENTRYOFF_ATTRIBS);
        bdio_fclose(fHandleIn);

        if(options & MODE_SET)
        {
            options <- options & attrmask;
            fAttribsOut <- fAttribsIn | options;
            bdio_fsetattr(Psourcefileext, fAttribsOut);
        }
        if(options & MODE_UNSET)
        {
            fAttribsOut <- fAttribsIn & options;
            bdio_fsetattr(Psourcefileext, fAttribsOut);
        }
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
    byte val;
    byte bit;

    result <- 0;

    if(getswitch(Poptions, "H") = 1)
    {
        result <- MODE_HELP;
    }
    else 
    {
        val <- peek8(Poptions);

        if(val = '-')
        {
            result <- MODE_UNSET | BDIO_FILE_ATTRIB_READ | BDIO_FILE_ATTRIB_WRITE | BDIO_FILE_ATTRIB_EXEC | BDIO_FILE_ATTRIB_SYSTEM;
            Poptions <- Poptions + 1;
        }
        else
        {
            if(val = '+')
            {
                result <- MODE_SET;
                Poptions <- Poptions + 1;
            }
        }

        val <- peek8(Poptions);

        while(val && (val != ' '))
        {
            if(val = 'S')
            {
                bit <- BDIO_FILE_ATTRIB_SYSTEM;
            }
            if(val = 'R')
            {
                bit <- BDIO_FILE_ATTRIB_READ;
            }
            if(val = 'W')
            {
                bit <- BDIO_FILE_ATTRIB_WRITE;
            }
            if(val = 'X')
            {
                bit <- BDIO_FILE_ATTRIB_EXEC;
            }

            if(result & MODE_SET)
            {
                result <- result | bit;
            }
            if(result & MODE_UNSET)
            {
                result <- result & (~bit);
                result <- result | MODE_UNSET;
            }

            Poptions <- Poptions + 1;
            val <- peek8(Poptions);
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
        printusage("set file attributes",
            "[+-][SRWX] set or unset attrib",
            0);
    }
    else
    {
        Pargs <- strnextword(Pargs);

        result <- argfile(Pargs, INFILEBDIONAME_ADDR);
        sourcedrv <- result;

        changeattributes(sourcedrv, INFILEBDIONAME_ADDR, options);
    }
}