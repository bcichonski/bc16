#code 0x5000
#heap 0x7000

#include std.b
#include bdosh.b
#include strings.b

#define CATBUFSECT_ADDR 0x7b00
#define FCATATTRIBSTRING_ADDR 0x7afa
#define FNAMESTRING_ADDR 0x7ad0
#define FEXT_LEN 0x03
#define FNAME_LEN 0x08

byte setAttrib(word Pstring, byte fcatAttribs, byte attrib, byte char)
{
    if((fcatAttribs & attrib) = attrib)
    {
        poke8(Pstring, char);
    }
}

byte listCatalogItem(word Pitem)
{
    byte fcatStartTrack;
    byte fcatStartSector;
    byte fcatSectorLen;
    byte fcatAttribs;
    word PfcatFileName;
    word fcatLengthInBytes;
    word PfcatAttribString;

    fcatSectorLen <- peek8(Pitem + BDIO_FCAT_ENTRYOFF_SECTLEN);

    if(fcatSectorLen > 0)
    {
        fcatStartTrack <- peek8(Pitem + BDIO_FCAT_ENTRYOFF_STARTTRACK);
        fcatStartSector <- peek8(Pitem + BDIO_FCAT_ENTRYOFF_STARTSECTOR);
        fcatAttribs <- peek8(Pitem + BDIO_FCAT_ENTRYOFF_ATTRIBS);
        PfcatFileName <- Pitem + BDIO_FCAT_ENTRYOFF_FNAME;

        strncpy(PfcatFileName + FNAME_LEN, FNAMESTRING_ADDR + FNAME_LEN + 1, BDIO_FCAT_ENTRY_NAMELEN);
        strncpy(PfcatFileName, FNAMESTRING_ADDR, FNAME_LEN);

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

        printf("%s %s %w %x %x %x%n", FNAMESTRING_ADDR, PfcatAttribString, fcatLengthInBytes, fcatStartTrack, fcatStartSector, fcatSectorLen);
    }
}

byte listCatalog(word PsectorBuf)
{
    word Pcurrent;

    Pcurrent <- PsectorBuf;

    while(Pcurrent < PsectorBuf + BDIO_SECTBUF_LEN)
    {
        listCatalogItem(Pcurrent);

        Pcurrent <- Pcurrent + BDIO_FCAT_ENTRY_LENGTH;
    }
}

byte main()
{
    word fHandle;
    byte sectRead;

    fHandle <- bdio_fbinopenr("DISC    CAT");

    if(fHandle < BDIO_FOPEN_FNAME_NOTFOUND)
    {
        sectRead <- bdio_fbinread(fHandle, CATBUFSECT_ADDR, 1);
        while(sectRead)
        {
            listCatalog(CATBUFSECT_ADDR);

            sectRead <- bdio_fbinread(fHandle, CATBUFSECT_ADDR, 1);
        }

        bdio_fclose(fHandle);
    }
    else
    {
        bdio_printexecres(fHandle);
    }
}