#code 0x5000
#heap 0x7000

#include std.b
#include bdosh.b
#include strings.b

#define CATBUFSECT_ADDR 0x7d80
#define FCATATTRIBSTRING_ADDR 0x7d50
#define FNAMESTRING_ADDR 0x7d60
#define FEXT_LEN 0x03
#define FNAME_LEN 0x08
#define MODE_SWITCH_SHOWALL 0x01
#define MODE_HELP 0x10
#define MODE_LS 0x20

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
            poke8(FNAMESTRING_ADDR + BDIO_FCAT_ENTRY_NAMELEN + 2, BNULL);

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

byte listCatalog(byte showall)
{
    word fHandle;
    byte sectRead;
    word Pcurrent;
    byte res;

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
}

byte main()
{
    word Pargs;
    byte showall;

    showall <- FALSE;
    upstring(BDIO_CMDPROMPTADDR);
    Pargs <- strnextword(BDIO_CMDPROMPTADDR);

    if(strncmp(Pargs, "-H", 3) = STRCMP_EQ)
    {
        printf("%s%n%s%n%s%n",
            "lists files",
            "-a show all files", 
            "-h print help");
    }
    else
    {
        if(strncmp(Pargs, "-A", 3) = STRCMP_EQ)
        {
            showall <- TRUE;
        }

        listCatalog(showall);
    }
}