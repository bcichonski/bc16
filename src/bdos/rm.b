#code 0x5000
#heap 0x7000

#include std.b
#include bdosh.b
#include strings.b

#define FCATBUF_ADDR 0x7800
#define INFILEBDIONAME_ADDR 0x77f0
#define DRIVEPRESENT 0x0100
#define MODE_HELP 0x10
#define MODE_FORCE 0x20
#define FCAT_COPY_ADDR 0x77c0

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

byte remove(byte sourcedrive, word Psourcefileext, byte options)
{
    byte currentDrive;
    byte activeDrive;
    byte fAttribsIn;
    byte fHandleIn;
    byte result;
    word Pfcatentry;
    word PfcatlastEntry;
    word tracksector;
    byte fcattrack;
    byte fcatsector;
    byte fcatLastEntryNo;
    byte fcatsectors;

    printf("removing %s:%s with options %x...%n", getdriveletter(sourcedrive), Psourcefileext, options);

    activeDrive <- bdio_getdrive();
    currentDrive <- changeDriveIfNeeded(activeDrive, sourcedrive, FALSE);

    fHandleIn <- bdio_fbinopenr(Psourcefileext);
    if(fHandleIn < BDIO_FOPEN_FNAME_NOTFOUND)
    {
        putsnl("a");
        fAttribsIn <- peek8(Pfcatentry + BDIO_FCAT_ENTRYOFF_ATTRIBS);
        if((options != MODE_FORCE) && (fAttribsIn & BDIO_FILE_ATTRIB_SYSTEM))
        {
            putsnl("error: cannot remove system file");
        }
        else
        {
            putsnl("b");
            fcatLastEntryNo <- peek8(BDIO_VAR_FCAT_FREEENTRY) - 1;
            fcatsector <- fcatLastEntryNo >> 3;
            tracksector <- bdio_tracksector_add(BDIO_FCAT_STARTTRACK, BDIO_FCAT_STARTSECTOR, fcatsector);
            fcattrack <- tracksector >> 8;
            fcatsector <- tracksector & 0xff;

            result <- bdio_readsect(fcattrack, fcatsector, FCATBUF_ADDR);

            if(result = FDD_RESULT_OK)
            {
                putsnl("c");
                Pfcatentry <- (fcatLastEntryNo & 0x07) << 4;
                Pfcatentry <- FCATBUF_ADDR + Pfcatentry;

                //copy fcat record without fno to temp buf
                memcpy(Pfcatentry + 1, FCAT_COPY_ADDR, BDIO_FCAT_ENTRY_LENGTH - 1);
                poke8(Pfcatentry + BDIO_FCAT_ENTRYOFF_SECTLEN, 0x00);

                result <- bdio_writesect(fcattrack, fcatsector, FCATBUF_ADDR);

                Pfcatentry <- #(BDIO_VAR_FCAT_PLASTFOUND);
                fcattrack <- peek8(BDIO_VAR_FCAT_SCAN_TRACK);
                fcatsector <- peek8(BDIO_VAR_FCAT_SCAN_SECT);
            
                bdio_fclose(fHandleIn);

                if(result = FDD_RESULT_OK)
                {
                    putsnl("d");
                    memcpy(FCAT_COPY_ADDR, Pfcatentry + 1, BDIO_FCAT_ENTRY_LENGTH - 1);                 

                    result <- bdio_writesect(fcattrack, fcatsector, BDIO_TAB_SCANSECTBUF);

                    if(result != FDD_RESULT_OK)
                    {
                        printf("error while saving fcat update: %x%n", result);
                    }
                }
            }

            if(result != FDD_RESULT_OK)
            {
                printf("error: %x%n", result);
            }    
        }  
    }
    else
    {
        bdio_printexecres(fHandleIn);
    }

    currentDrive <- changeDriveIfNeeded(currentDrive, activeDrive, FALSE);
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
    result <- 0;

    if(strncmp(Poptions, "-F", 2) = STRCMP_EQ)
    {
        result <- MODE_FORCE;
    }

    if(strncmp(Poptions, "-H", 2) = STRCMP_EQ)
    {
        result <- MODE_HELP;
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
            "remove file",
            "[-f] force", 
            "[d:]srcfname.ext");
    }
    else
    {
        if(options)
        {
            Pargs <- Pargs + 3;
        }

        result <- getdrive(Pargs);
        poke8(Pargs - 1, NULLCHAR);
        if(result & DRIVEPRESENT)
        {
            Pargs <- Pargs + 2;
        }

        PsrcFileNameExt <- Pargs;
        sourcedrv <- result;

        fnormalize(PsrcFileNameExt, INFILEBDIONAME_ADDR);

        remove(sourcedrv, INFILEBDIONAME_ADDR, options);
    }
}