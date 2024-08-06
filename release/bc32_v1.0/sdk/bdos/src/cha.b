#code 0x5000
#heap 0x7000

#include std.b
#include bdosh.b
#include strings.b

#define MODE_SET 0x10
#define MODE_UNSET 0x20
#define MODE_HELP 0x40
#define DRIVEPRESENT 0x0100
#define INFILEBDIONAME_ADDR 0x77f0

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

    fHandleIn <- bdio_fbinopenr(Psourcefileext);
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
    word PsrcFileNameExt;
    byte sourcedrv;
    byte len;
    byte options;

    upstring(BDIO_CMDPROMPTADDR);
    Pargs <- strnextword(BDIO_CMDPROMPTADDR);
    options <- getoptions(Pargs);

    if(options & MODE_HELP)
    {
        printf("%s%n%s%n",
            "set file attributes",
            "[+-][SRWX] set or unset attrib");
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

        changeattributes(sourcedrv, INFILEBDIONAME_ADDR, options);
    }
}