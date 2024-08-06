#code 0x5000
#heap 0x7000

#include std.b
#include bdosh.b
#include strings.b

#define CATBUFSECT_ADDR 0x7880
#define FCATATTRIBSTRING_ADDR 0x7850
#define FNAMESTRING_ADDR 0x7860
#define FEXT_LEN 0x03
#define FNAME_LEN 0x08
#define MODE_SWITCH_SHOWALL 0x01
#define MODE_HELP 0x10
#define MODE_LS 0x20

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
        result <- BDIO_DRIVEA;
    }
    else
    {
        if(strncmp(Pargs, "B:", 2) = STRCMP_EQ)
        {
            result <- BDIO_DRIVEB;
        }
        else
        {
            result <- bdio_getdrive();
        }
    }
    return result;
}

byte setAttrib(word Pstring, byte fcatAttribs, byte attrib, byte char)
{
    if((fcatAttribs & attrib) = attrib)
    {
        poke8(Pstring, char);
    }
}

byte listCatalogItem(word Pitem, byte showall)
{
    byte res;
    byte fcatStartTrack;
    byte fcatStartSector;
    byte fcatSectorLen;
    byte fcatAttribs;
    word PfcatFileName;
    word fcatLengthInBytes;
    word PfcatAttribString;

    fcatSectorLen <- peek8(Pitem + BDIO_FCAT_ENTRYOFF_SECTLEN);
    res <- FALSE;

    if(fcatSectorLen > 0)
    {
        fcatAttribs <- peek8(Pitem + BDIO_FCAT_ENTRYOFF_ATTRIBS);

        if(showall || ((fcatAttribs & BDIO_FILE_ATTRIB_SYSTEM) != BDIO_FILE_ATTRIB_SYSTEM))
        {
            fcatStartTrack <- peek8(Pitem + BDIO_FCAT_ENTRYOFF_STARTTRACK);
            fcatStartSector <- peek8(Pitem + BDIO_FCAT_ENTRYOFF_STARTSECTOR);

            PfcatFileName <- Pitem + BDIO_FCAT_ENTRYOFF_FNAME;

            strncpy(PfcatFileName, FNAMESTRING_ADDR, FNAME_LEN);
            strncpy(PfcatFileName + FNAME_LEN, FNAMESTRING_ADDR + FNAME_LEN + 1, 3);

            poke8(FNAMESTRING_ADDR + FNAME_LEN, '.');
            poke8(FNAMESTRING_ADDR + BDIO_FCAT_ENTRY_NAMELEN + 1, BNULL);

            fcatLengthInBytes <- fcatSectorLen * BDIO_SECTBUF_LEN;

            PfcatAttribString <- FCATATTRIBSTRING_ADDR;
            mfill(PfcatAttribString, 4, '-');

            setAttrib(PfcatAttribString, fcatAttribs, BDIO_FILE_ATTRIB_SYSTEM, 'S');
            setAttrib(PfcatAttribString + 1, fcatAttribs, BDIO_FILE_ATTRIB_READ, 'R');
            setAttrib(PfcatAttribString + 2, fcatAttribs, BDIO_FILE_ATTRIB_WRITE, 'W');
            setAttrib(PfcatAttribString + 3, fcatAttribs, BDIO_FILE_ATTRIB_EXEC, 'X');

            poke8(PfcatAttribString + 4, BNULL);

            printf("%s %s %w %x %x %x%n", 
                FNAMESTRING_ADDR, 
                PfcatAttribString, 
                fcatLengthInBytes, 
                fcatStartTrack, 
                fcatStartSector, 
                fcatSectorLen);
        }

        res <- TRUE;
    }

    return res;
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

byte listCatalog(byte showall, byte targetdrive)
{
    word fHandle;
    byte sectRead;
    word Pcurrent;
    byte res;
    byte currentdrive;
    byte activedrive;

    printf("listing files of drive %s:%n", getdriveletter(targetdrive));
    activedrive <- bdio_getdrive();
    currentdrive <- changeDriveIfNeeded(activedrive, targetdrive, FALSE);

    fHandle <- bdio_fbinopenr("DISC    CAT");
    res <- TRUE;
    if(fHandle < BDIO_FOPEN_FNAME_NOTFOUND)
    {
        sectRead <- bdio_fbinread(fHandle, CATBUFSECT_ADDR, 1);

        while(sectRead && res)
        {
            Pcurrent <- CATBUFSECT_ADDR;

            while(res && (Pcurrent < CATBUFSECT_ADDR + BDIO_SECTBUF_LEN))
            {
                res <- listCatalogItem(Pcurrent, showall);

                Pcurrent <- Pcurrent + BDIO_FCAT_ENTRY_LENGTH;
            }

            if(res) {
                sectRead <- bdio_fbinread(fHandle, CATBUFSECT_ADDR, 1);
            }
        }

        bdio_fclose(fHandle);
    }
    else
    {
        bdio_printexecres(fHandle);
    }

    byte freeTrack;
    byte freeSector;
    byte freeEntry;
    word freeSectors;
    byte freeEntries;

    freeTrack <- peek8(BDIO_VAR_FCAT_FREETRACK);
    freeSector <- peek8(BDIO_VAR_FCAT_FREESECT);
    freeEntry <- peek8(BDIO_VAR_FCAT_FREEENTRY);

    freeSectors <- (FDD_TRACKS - freeTrack) * FDD_SECTORS + freeSector;
    freeEntries <- BDIO_FCAT_LASTENTRY - freeEntry;

    printf("%x catalog entries free; %w sectors free...%n", freeEntries, freeSectors);

    changeDriveIfNeeded(currentdrive, activedrive, FALSE);
}

byte main()
{
    word Pargs;
    byte showall;

    showall <- FALSE;
    upstring(BDIO_CMDPROMPTADDR);
    Pargs <- strnextword(BDIO_CMDPROMPTADDR);

    if(strncmp(Pargs, "-H", 2) = STRCMP_EQ)
    {
        printf("%s%n%s%n%s%n",
            "lists files",
            "-a show all files", 
            "-h print help");
    }
    else
    {
        if(strncmp(Pargs, "-A", 2) = STRCMP_EQ)
        {
            showall <- TRUE;
            Pargs <- Pargs + 3;
        }

        byte targetdrive;
        targetdrive <- getdrive(Pargs);

        listCatalog(showall, targetdrive);
    }
}