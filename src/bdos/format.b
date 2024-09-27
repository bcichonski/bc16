#code 0x5000
#heap 0x7000

#include std.b
#include bdosh.b
#include strings.b

#define FILEBUFSECT_ADDR 0x7c00
#define FILEBUFSECT_LEN 0x40
#define DRIVEPRESENT 0x0100
#define FORMATMODE_QUICK 0x10
#define FORMATMODE_HELP 0x20

#define CHECK_BDOS_SIG_OFFSET 0x007c
#define CHECK_BDOS_SIG_PATTERN 0xbd05

#define CHECKERROR_BOOTBINREADERROR 0xe0
#define CHECKERROR_BADBOOTSECTOR 0xe1
#define CHECKERROR_NOBDOSSYS 0xe2

#define CHECK_BOOTBINOK 0xc0
#define CHECK_ALLOK 0xcf

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

byte copy(byte sourcedrive, word Psourcefileext, byte targetdrive, word Ptargetfileext)
{
    byte currentDrive;
    byte fHandleIn;
    byte fHandleOut;
    byte sectorsread;
    byte fAttribsIn;
    byte result;
    word Pfcatentry;
    byte nowritemask;

    printf("%ncopying %s:%s to %s:%s%n", getdriveletter(sourcedrive), Psourcefileext, getdriveletter(targetdrive), Ptargetfileext);

    currentDrive <- bdio_getdrive();
    currentDrive <- changeDriveIfNeeded(currentDrive, sourcedrive, FALSE);
    result <- FALSE;
    nowritemask <- BDIO_FILE_ATTRIB_EXEC | BDIO_FILE_ATTRIB_SYSTEM | BDIO_FILE_ATTRIB_READ;

    fHandleIn <- bdio_fbinopenr(Psourcefileext);
    if(fHandleIn < BDIO_FOPEN_FNAME_NOTFOUND)
    {
        Pfcatentry <- #(BDIO_VAR_FCAT_PLASTFOUND);
        fAttribsIn <- peek8(Pfcatentry + BDIO_FCAT_ENTRYOFF_ATTRIBS);
       
        currentDrive <- changeDriveIfNeeded(currentDrive, targetdrive, FALSE);

        result <- bdio_fcreate(Ptargetfileext, fAttribsIn);
        if(!result)
        {
            fHandleOut <- bdio_fbinopenw(Ptargetfileext);

            if(fHandleOut < BDIO_FOPEN_FNAME_NOTFOUND)
            {
                currentDrive <- changeDriveIfNeeded(currentDrive, sourcedrive, TRUE);
                sectorsread <- bdio_fbinread(fHandleIn, FILEBUFSECT_ADDR, FILEBUFSECT_LEN);
                result <- 1;

                while(sectorsread && result)
                {
                    currentDrive <- changeDriveIfNeeded(currentDrive, targetdrive, TRUE);

                    result <- bdio_fbinwrite(fHandleOut, FILEBUFSECT_ADDR, sectorsread);

                    if(result)
                    {
                        currentDrive <- changeDriveIfNeeded(currentDrive, sourcedrive, TRUE);
                        sectorsread <- bdio_fbinread(fHandleIn, FILEBUFSECT_ADDR, FILEBUFSECT_LEN);
                    }
                    else
                    {
                        printf("error writing sectors%n");
                    }
                }

                currentDrive <- changeDriveIfNeeded(currentDrive, targetdrive, TRUE);
                bdio_fclose(fHandleOut);
                bdio_fsetattr(Psourcefileext, fAttribsIn & nowritemask);
                result <- FALSE;
            }
            else
            {
                bdio_printexecres(fHandleOut);
            }
        }
        else
        {
            bdio_printexecres(result);
        }

        currentDrive <- changeDriveIfNeeded(currentDrive, sourcedrive, FALSE);
        bdio_fclose(fHandleIn);
    }
    else
    {
        bdio_printexecres(fHandleIn);
    }

    return result;
}

byte getoptions(word Poptions)
{
    byte result;
    result <- 0;

    if(strncmp(Poptions, "-Q", 2) = STRCMP_EQ)
    {
        result <- result | FORMATMODE_QUICK;
    }

    if(strncmp(Poptions, "-H", 2) = STRCMP_EQ)
    {
        result <- FORMATMODE_HELP;
    }

    return result;
}

byte checksourcedrive()
{
    byte result;
    byte fhandle;
    byte sectorsread;
    word bdosSignature;

    //1. it must be a bdos disc
    //meaning boot sector should have bdos signature

    result <- bdio_readsect(0x00, 0x00, FILEBUFSECT_ADDR);
    if(result = FDD_RESULT_OK)
    {
        bdosSignature <- #(FILEBUFSECT_ADDR + CHECK_BDOS_SIG_OFFSET);
        result <- CHECKERROR_BADBOOTSECTOR;
        if(bdosSignature = CHECK_BDOS_SIG_PATTERN)
        {
            result <- CHECK_BOOTBINOK;
        }
    }
    else 
    {
        result <- CHECKERROR_BOOTBINREADERROR;
    }

    if(result = CHECK_BOOTBINOK)
    {
        //2. it must have BDOS.SYS present
        result <- CHECKERROR_NOBDOSSYS;

        fhandle <- bdio_fbinopenr("BDOS    SYS");
        if(fhandle < BDIO_FOPEN_FNAME_NOTFOUND)
        {
            result <- CHECK_ALLOK;
        }
        bdio_fclose(fhandle);
    }

    return result;
}

byte formatcatmem(word Pfcatmembuf, byte fcatEntryNo)
{
    word Plast;
    byte fcatNo;
    fcatNo <- fcatEntryNo;
    Plast <- Pfcatmembuf + BDIO_SECTBUF_LEN;

    while(Pfcatmembuf < Plast)
    {
        poke8(Pfcatmembuf + BDIO_FCAT_ENTRYOFF_NUMBER, fcatNo);
        poke8(Pfcatmembuf + BDIO_FCAT_ENTRYOFF_SECTLEN, 0x00);

        fcatNo <- fcatNo + 1;
        Pfcatmembuf <- Pfcatmembuf + BDIO_FCAT_ENTRY_LENGTH;
    }

    return fcatNo;
}

byte newfcatentry(word PfcatEntry, byte no, byte track, byte sector, byte len, word Pfilenameext)
{
    poke8(PfcatEntry + BDIO_FCAT_ENTRYOFF_NUMBER, no);
    poke8(PfcatEntry + BDIO_FCAT_ENTRYOFF_STARTTRACK, track);
    poke8(PfcatEntry + BDIO_FCAT_ENTRYOFF_STARTSECTOR, sector);
    poke8(PfcatEntry + BDIO_FCAT_ENTRYOFF_SECTLEN, len);
    poke8(PfcatEntry + BDIO_FCAT_ENTRYOFF_ATTRIBS, BDIO_FILE_ATTRIB_SYSTEM | BDIO_FILE_ATTRIB_READ);
    strncpy(Pfilenameext, PfcatEntry + BDIO_FCAT_ENTRYOFF_FNAME, BDIO_FCAT_ENTRY_NAMELEN);
}

byte createcatalog()
{
    word PcatEntry;
    word tracksector;
    byte track;
    byte sector;
    byte result;
    byte fcatEntryNo;
    byte error;

    if(result = FDD_RESULT_OK)
    {
        track <- BDIO_FCAT_STARTTRACK;
        sector <- BDIO_FCAT_STARTSECTOR;
        fcatEntryNo <- 0;
        puts("creating catalogue");
        result <- bdio_readsect(track, sector, FILEBUFSECT_ADDR);

        if(result = FDD_RESULT_OK)
        {
            fcatEntryNo <- formatcatmem(FILEBUFSECT_ADDR, fcatEntryNo);

            newfcatentry(FILEBUFSECT_ADDR, 0x00, 0x00, 0x00, 0x01, "BOOT    BIN");
            newfcatentry(FILEBUFSECT_ADDR + BDIO_FCAT_ENTRY_LENGTH, 0x01, 0x00, 0x01, (BDIO_FCAT_ENDTRACK + 1) * 16 - 1, "DISC    CAT");

            result <- bdio_writesect(track, sector, FILEBUFSECT_ADDR);

            if(result = FDD_RESULT_OK)
            {
                puts(".");

                tracksector <- bdio_tracksector_add(track, sector, 1);
                track <- tracksector >> 8;
                sector <- tracksector & 0x0f;
                error <- FALSE;

                while((track <= BDIO_FCAT_ENDTRACK) && (!error))
                {
                    result <- bdio_readsect(track, sector, FILEBUFSECT_ADDR);
                    error <- TRUE;
                    if(result = FDD_RESULT_OK)
                    {
                        fcatEntryNo <- formatcatmem(FILEBUFSECT_ADDR, fcatEntryNo);

                        result <- bdio_writesect(track, sector, FILEBUFSECT_ADDR);
                        if(result = FDD_RESULT_OK)
                        {
                            if((sector & 0x07) = 0x07)
                            {
                                puts(".");
                            }

                            tracksector <- bdio_tracksector_add(track, sector, 1);
                            track <- tracksector >> 8;
                            sector <- tracksector & 0x0f;
                            error <- FALSE;
                        }
                    }
                }
            }
        }
    }

    return result;
}

byte format(byte sourcedrive, byte targetdrive, byte options)
{
    byte currentDrive;
    byte result;
    word Pfname;

    currentDrive <- bdio_getdrive();
    result <- TRUE;
    
    if(options & FORMATMODE_QUICK)
    {
        currentDrive <- changeDriveIfNeeded(currentDrive, targetdrive, FALSE);
        result <- checksourcedrive();
        if(result = CHECK_ALLOK)
        {
            //we need to create empty DISC.CAT
            result <- createcatalog();
            currentDrive <- changeDriveIfNeeded(currentDrive, sourcedrive, FALSE);
        }
        else
        {
            putsnl("drive is not a system disc%n");
        }
    }
    else
    {
        //normal wipe mode
        //sourcedrive must be a system disk
        currentDrive <- changeDriveIfNeeded(currentDrive, sourcedrive, FALSE);
        result <- checksourcedrive();
        if(result = CHECK_ALLOK)
        {
            //copy bootsector
            printf("copying bootsector...%n");

            result <- bdio_readsect(0x00, 0x00, FILEBUFSECT_ADDR);
            currentDrive <- changeDriveIfNeeded(currentDrive, targetdrive, TRUE);

            if(result = FDD_RESULT_OK)
            {
                result <- bdio_writesect(0x00, 0x00, FILEBUFSECT_ADDR);
            }

            //we need to create empty DISC.CAT
            result <- createcatalog();
            currentDrive <- changeDriveIfNeeded(currentDrive, sourcedrive, FALSE);

            if(result = FDD_RESULT_OK)
            {
                //now that we have the catalog we can start copying files
                Pfname <- "BDOS    SYS";
                result <- copy(sourcedrive, Pfname, targetdrive, Pfname);
                if(!result)
                {
                    Pfname <- "LS      PRG";
                    result <- copy(sourcedrive, Pfname, targetdrive, Pfname);
                }
                if(!result)
                {
                    Pfname <- "CP      PRG";
                    result <- copy(sourcedrive, Pfname, targetdrive, Pfname);
                }
                if(!result)
                {
                    Pfname <- "FORMAT  PRG";
                    result <- copy(sourcedrive, Pfname, targetdrive, Pfname);
                }
                if(!result)
                {
                    Pfname <- "RM      PRG";
                    result <- copy(sourcedrive, Pfname, targetdrive, Pfname);
                }
                if(!result)
                {
                    Pfname <- "CHA     PRG";
                    result <- copy(sourcedrive, Pfname, targetdrive, Pfname);
                }
                if(!result)
                {
                    Pfname <- "CAT     PRG";
                    result <- copy(sourcedrive, Pfname, targetdrive, Pfname);
                }
            }
        }
        else
        {
            printf("error %x: source drive is not a system disc%n", result);
        }
    }

    return result;
}

byte main()
{
    word Pargs;
    word result;
    word Poptions;
    byte sourcedrv;
    byte targetdrv;
    byte options;

    upstring(BDIO_CMDPROMPTADDR);
    Pargs <- strnextword(BDIO_CMDPROMPTADDR);
    poke8(Pargs - 1, NULLCHAR);

    Poptions <- Pargs;
    options <- getoptions(Poptions);

    if(options = FORMATMODE_HELP)
    {
        printf("%s%n%s%n%s%n",
            "format disc",
            "d: drive", 
            "-q quick");
    }
    else
    {
        if(options & FORMATMODE_QUICK)
        {
            Pargs <- Pargs + 3;
        }

        result <- getdrive(Pargs);
        
        targetdrv <- result;
        sourcedrv <- BDIO_DRIVEB - targetdrv;
        
        printf("formatting disc %s...%n", getdriveletter(targetdrv));
        result <- format(sourcedrv, targetdrv, options);
        if(result > 0)
        {
            printf("format error: %x", result);
        }
        putnl();
    }
}