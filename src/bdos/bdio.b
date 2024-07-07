#define FDD_PORT 0x08
#define FDD_TRACKS 0x40
#define FDD_SECTORS 0x10

#define FDD_CMD_CONFIG 0x0f1
#define FDD_CMD_READ 0xf2
#define FDD_CMD_WRITE 0xf3
#define FDD_CMD_SETDRVA 0xfa
#define FDD_CMD_SETDRVB 0xfb

#define FDD_STATE_READY 0x10

#define FDD_RESULT_OK 0x00
#define BDIO_RESULT_ENDOFCAT 0xc0

#define BDIO_DRIVEA 0x00
#define BDIO_DRIVEB 0x01
#define BDIO_FCAT_STARTTRACK 0x08
#define BDIO_FCAT_ENDTRACK 0x09
#define BDIO_FCAT_ENTRYOFF_NUMBER 0x00
#define BDIO_FCAT_ENTRYOFF_STARTTRACK 0x01
#define BDIO_FCAT_ENTRYOFF_STARTSECTOR 0x02
#define BDIO_FCAT_ENTRYOFF_SECTLEN 0x03
#define BDIO_FCAT_ENTRYOFF_ATTRIBS 0x04
#define BDIO_FCAT_ENTRYOFF_FNAME 0x05
#define BDIO_FCAT_ENTRY_LENGTH 0x10
#define BDIO_FCAT_ENTRY_NAMELEN 11
#define BDIO_FCAT_FREEENTRY_FULL 0xff

#define BDIO_FREEMAP_FULL 0x0000
#define BDIO_FNAME_NOTFOUND 0x0000

#define BDIO_FDESCRIPTOROFF_NUMBER 0x00
#define BDIO_FDESCRIPTOROFF_FCATENTRYNO 0x01
#define BDIO_FDESCRIPTOROFF_CURRTRACK 0x02
#define BDIO_FDESCRIPTOROFF_CURRSECT 0x03
#define BDIO_FDESCRIPTOROFF_CURRSEQ 0x04
#define BDIO_FDESCRIPTOROFF_SEQLEN 0x05
#define BDIO_FDESCRIPTOROFF_FCATTRACK 0x06
#define BDIO_FDESCRIPTOROFF_FCATSECT 0x07
#define BDIO_FDESCRIPTOR_READ_MAX 0x03
#define BDIO_FDESCRIPTOR_LEN 0x08
#define BDIO_FDESCRIPTOR_NUMBERFREE 0x00
#define BDIO_FDESCRIPTOR_NUMBERWRITE 0x10
#define BDIO_FDESCRIPTOR_NUMBERREAD 0x20
#define BDIO_FDESCRIPTOR_NUMBERFULL 0xff

#define BDIO_FOPEN_FNAME_NOTFOUND 0xe0
#define BDIO_FOPEN_FDD_NOT_READY 0xe1
#define BDIO_FOPEN_ATTR_NOREAD 0xe3

#define BDIO_FCLOSE_FDESC_NOTFOUND 0xe2

#define BDIO_FEXEC_ATTR_NOEXEC 0xe4
#define BDIO_FEXEC_FDESCFCAT_ERR 0xe5
#define BDIO_FEXEC_OUTOFMEM 0xe6
#define BDIO_FEXEC_SECTFAIL 0xe7
#define BDIO_FEXEC_OK 0x00

#define BDIO_FILE_ATTRIB_READ 0x01
#define BDIO_FILE_ATTRIB_WRITE 0x02
#define BDIO_FILE_ATTRIB_EXEC 0x04
#define BDIO_FILE_ATTRIB_SYSTEM 0x80

#define BDIO_VAR_LASTERROR 0x4e00
#define BDIO_VAR_ACTIVEDRV 0x4e01
#define BDIO_VAR_FCAT_SCAN_TRACK 0x4e02
#define BDIO_VAR_FCAT_SCAN_SECT 0x4e03
#define BDIO_VAR_FCAT_FREEENTRY 0x4e04
#define BDIO_VAR_FCAT_FREETRACK 0x4e05
#define BDIO_VAR_FCAT_FREESECT 0x4e06
#define BDIO_VAR_FCAT_PLASTFOUND 0x4e08
#define BDIO_VAR_FCAT_NEWENTRYADDR 0x4e10
#define BDIO_VAR_FDESCTAB_WRITE 0x4e12
#define BDIO_VAR_FDESCTAB_READ 0x4e1a

#define BDIO_CMDPROMPTADDR 0x4ec0
#define BDIO_CMDPROMPTLEN 0x40
#define BDIO_TMP_SECTBUF 0x0e80
#define BDIO_TAB_SCANSECTBUF 0x4e40
#define BDIO_SECTBUF_LEN 0x80

#define BDIO_USERMEM 0x5000
#define BDIO_NULL 0x0000

byte bdio_getstate()
{
    //reads the fdd state

    FDD_PORT;
    asm "in a, #ci";
    asm "mov ci, a";
}

byte bdio_checkstate()
{
    //checks the fdd state
    //returns FDD_RESULT_OK if ok
    //stores last error in BDIO_VAR_LASTERROR

    byte fddstate;
    fddstate <- bdio_getstate();
    poke8(BDIO_VAR_LASTERROR, fddstate);
    byte fddresult;
    fddresult <- FDD_RESULT_OK;
    if (fddstate != FDD_STATE_READY)
    {
        fddresult <- fddstate;
    }
    return fddresult;
}

byte bdio_configure(word Pmembuf)
{
    //sets fdd dma address to Pmembuf
    //returns fdd state

    FDD_PORT;
    asm "psh ci";
    FDD_CMD_CONFIG;
    asm "psh ci";
    Pmembuf;
    asm "pop a";
    asm "pop di";
    asm "out #di, a";
    asm "mov a, cs";
    asm "out #di, a";
    asm "mov a, ci";
    asm "out #di, a";

    return bdio_checkstate();
}

word bdio_get_procstackhead()
{
    asm "mov cs, ss";
    asm "mov ci, si";
}

word bdio_get_sysstackhead()
{
    asm ".mv dsdi, :sys_stackhead";
    asm "cal :peek16";
}

byte bdio_iosec(byte fddcmd, byte track, byte sector, word Pmembuf) 
{
    //low level function to configure dma and read or write sector there
    //returns fdd state

    byte result;
    result <- bdio_configure(Pmembuf);

    if (result = FDD_RESULT_OK)
    {
        sector;
        asm "psh ci";
        track;
        asm "psh ci";
        FDD_PORT;
        asm "psh ci";
        fddcmd;
        asm "psh ci";
        asm "pop a";
        asm "pop di";
        asm "out #di, a";
        asm "pop a";
        asm "out #di, a";
        asm "pop a";
        asm "out #di, a";

        result <- bdio_checkstate();
    }

    return result;
}

byte bdio_readsec(byte track, byte sector, word Pmembuf) 
{
    // reads sector to given mem address
    // returns fdd state
    byte result;
    result <- bdio_iosec(FDD_CMD_READ, track, sector, Pmembuf);
    return result;
}

byte bdio_writesec(byte track, byte sector, word Pmembuf) 
{
    // writes sector from given mem address
    // returns fdd state

    return bdio_iosec(FDD_CMD_WRITE, track, sector, Pmembuf);
}

byte bdio_getdrive()
{
    // returns active drive as os remembers
    return peek8(BDIO_VAR_ACTIVEDRV);
}

word bdio_tracksector_get(byte track, byte sector)
{
    word result;
    result <- (track << 4) | sector;
    return result;
}

word bdio_tracksector_add(byte track, byte sector, byte sectorlen)
{
    //calculates track sector that is a result of adding sectorlen sectors to given track/sector
    //returns word value in which first byte is track, second is sector
    word result;
    word sectors;

    sectors <- (track << 4) | sector;
    sectors <- sectors + sectorlen;
    
    result <- (sectors >> 4) << 8;
    result <- result | (sectors & 0x0f);

    return result;
}

byte bdio_fcat_scanfirst(word PsectorBuf)
{
    // method that initiates catalog scan
    // reads first sector to BDIO_TMP_SECTBUF
    // stores current track and sector in BDIO_VAR_FCAT_SCAN_TRACK and BDIO_VAR_FCAT_SCAN_SECT
    // returns fdd state

    byte track;
    byte sector;
    byte result;

    track <- BDIO_FCAT_STARTTRACK;
    sector <- 0;

    result <- bdio_readsec(track, sector, PsectorBuf);

    if (result = FDD_RESULT_OK) 
    {
        poke8(BDIO_VAR_FCAT_SCAN_TRACK, track);
        poke8(BDIO_VAR_FCAT_SCAN_SECT, sector);
    }

    return result;
}

byte bdio_fcat_scannext(word PsectorBuf)
{
    // method continues catalog read
    // reads next sector to BDIO_TMP_SECTBUF
    // stores current track and sector in BDIO_VAR_FCAT_SCAN_TRACK and BDIO_VAR_FCAT_SCAN_SECT
    // returns fdd state or BDIO_RESULT_ENDOFCAT

    byte track;
    byte sector;
    byte result;
    word tracksector;
    
    track <- peek8(BDIO_VAR_FCAT_SCAN_TRACK);
    sector <- peek8(BDIO_VAR_FCAT_SCAN_SECT);
    result <- FDD_RESULT_OK;

    tracksector <- bdio_tracksector_add(track, sector, 1);
    track <- tracksector >> 8;
    sector <- tracksector & 0xff;

    if(track > BDIO_FCAT_ENDTRACK)
    {
        result <- BDIO_RESULT_ENDOFCAT;
    }
    
    if(result = FDD_RESULT_OK)
    {
        result <- bdio_readsec(track, sector, PsectorBuf);

        if (result = FDD_RESULT_OK) 
        {
            poke8(BDIO_VAR_FCAT_SCAN_TRACK, track);
            poke8(BDIO_VAR_FCAT_SCAN_SECT, sector);
        }
    }

    return result;
}

byte bdio_fcat_scanmem(word PsectorBuf)
{
    byte freeentry;
    byte freetrack;
    byte freesector;
    word Pentry;
    word PlastAddr;
    word freetracksector;
    byte currentry;
    byte currtrack;
    byte currsector;
    byte currsectlen;
    word currfreetracksector;

    freeentry <- peek8(BDIO_VAR_FCAT_FREEENTRY);
    freetrack <- peek8(BDIO_VAR_FCAT_FREETRACK);
    freesector <- peek8(BDIO_VAR_FCAT_FREESECT);

    freetracksector <- bdio_tracksector_get(freetrack, freesector);

    Pentry <- PsectorBuf;
    PlastAddr <- PsectorBuf + BDIO_SECTBUF_LEN;

    while(Pentry < PlastAddr)
    {
        currsectlen <- peek8(Pentry + BDIO_FCAT_ENTRYOFF_SECTLEN);
        currentry <- peek8(Pentry + BDIO_FCAT_ENTRYOFF_NUMBER);

        if(currsectlen > 0)
        {
            currtrack <- peek8(Pentry + BDIO_FCAT_ENTRYOFF_STARTTRACK);
            currsector <- peek8(Pentry + BDIO_FCAT_ENTRYOFF_STARTSECTOR);

            currfreetracksector <- bdio_tracksector_add(currtrack, currsector, currsectlen + 1);
            
            if (freetracksector < currfreetracksector)
            {
                freetracksector <- currfreetracksector;
                currtrack <- freetracksector >> 8;
                currsector <- freetracksector & 0x0f;     

                poke8(BDIO_VAR_FCAT_FREETRACK, currtrack);
                poke8(BDIO_VAR_FCAT_FREESECT, currsector);
            }
        }
        else
        {
            if (currentry < freeentry)
            {
                freeentry <- currentry;
                poke8(BDIO_VAR_FCAT_FREEENTRY, freeentry);
            }
        }

        Pentry <- Pentry + BDIO_FCAT_ENTRY_LENGTH;
    }
}

word bdio_fcat_ffindmem(word Pfnameext, word PsectorBuf)
{
    //looks in loaded to memory at PsectorBuf fcat sector 
    //a fcat entry with given name
    //returns BDIO_FNAME_NOTFOUND or address of the matching entry
    word Pentry;
    word PlastAddr;
    byte currentry;
    byte currsectlen;
    word Pcurrfnameext;
    byte strcmp;
    byte found;
    
    Pentry <- PsectorBuf;
    PlastAddr <- PsectorBuf + BDIO_SECTBUF_LEN;
    found <- FALSE;

    while((Pentry < PlastAddr) && !found)
    {
        currsectlen <- peek8(Pentry + BDIO_FCAT_ENTRYOFF_SECTLEN);
        currentry <- peek8(Pentry + BDIO_FCAT_ENTRYOFF_NUMBER);

        if(currsectlen > 0)
        {
            Pcurrfnameext <- Pentry + BDIO_FCAT_ENTRYOFF_FNAME;

            strcmp <- strncmp(Pfnameext, Pcurrfnameext, BDIO_FCAT_ENTRY_NAMELEN);

            found <- (strcmp = STRCMP_EQ);
        }

        Pentry <- Pentry + BDIO_FCAT_ENTRY_LENGTH;
    }

    if(found)
    {
        Pentry <- Pentry - BDIO_FCAT_ENTRY_LENGTH;
    }
    else
    {
        Pentry <- BDIO_FNAME_NOTFOUND;
    }

    return Pentry;
}

byte bdio_fcat_read()
{
    //reads file catalog
    //initializes variables BDIO_VAR_FCAT_FREEENTRY, BDIO_VAR_FCAT_FREETRACK, BDIO_VAR_FCAT_FREESECT

    byte result;

    poke8(BDIO_VAR_FCAT_FREEENTRY, BDIO_FCAT_FREEENTRY_FULL);
    poke8(BDIO_VAR_FCAT_FREETRACK, 0x00);
    poke8(BDIO_VAR_FCAT_FREESECT, 0x00);

    result <- bdio_fcat_scanfirst(BDIO_TMP_SECTBUF);

    while(result = FDD_RESULT_OK)
    {
        bdio_fcat_scanmem(BDIO_TMP_SECTBUF);

        result <- bdio_fcat_scannext(BDIO_TMP_SECTBUF);
    }

    if(result = BDIO_RESULT_ENDOFCAT)
    {
        result <- FDD_RESULT_OK;
    }

    if(peek8(BDIO_VAR_FCAT_FREEENTRY) = BDIO_FCAT_FREEENTRY_FULL)
    {
        result <- BDIO_RESULT_ENDOFCAT;
    }

    putb(peek8(BDIO_VAR_FCAT_FREETRACK));
    putb(peek8(BDIO_VAR_FCAT_FREESECT));
    putb(peek8(BDIO_VAR_FCAT_FREEENTRY));
    putnl();

    return result;
}

word bdio_ffindfile(word Pfnameext)
{
    //reads file catalog
    //looking for fcat entry with given file name
    //returns BDIO_FNAME_NOTFOUND if no file found
    //or address where the fcat entry resides in loaded fcat sector

    byte fddres;
    word result;

    result <- BDIO_FNAME_NOTFOUND;
    fddres <- bdio_fcat_scanfirst(BDIO_TAB_SCANSECTBUF);

    while((fddres = FDD_RESULT_OK) && (result = BDIO_FNAME_NOTFOUND))
    {
        result <- bdio_fcat_ffindmem(Pfnameext, BDIO_TAB_SCANSECTBUF);

        if(result = BDIO_FNAME_NOTFOUND)
        {
            fddres <- bdio_fcat_scannext(BDIO_TAB_SCANSECTBUF);
        }
    }

    poke16(BDIO_VAR_FCAT_PLASTFOUND, result);

    return result;
}

byte bdio_new_fcat(byte attribs)
{
    //creates a new entry in fcat table
    //and reads the proper sector of fcat table to BDIO_TMP_SECTBUF
    //memory address of that entry is BDIO_VAR_FCAT_NEWENTRYADDR
    //track and sector in which this entry resides is taken from BDIO_VAR_FCAT_FREETRACK and BDIO_VAR_FCAT_FREESECT
    //initializes entry with the start track and sector
    //returns fdd state

    byte result;
    byte entryNo;
    byte track;
    byte sector;
    word tracksector;
    word Pentry;

    result <- FDD_RESULT_OK;
    entryNo <- peek8(BDIO_VAR_FCAT_FREEENTRY);

    if(entryNo != BDIO_FCAT_FREEENTRY_FULL)
    {
        sector <- entryNo >> 3;
        tracksector <- bdio_tracksector_add(BDIO_FCAT_STARTTRACK, 0x00, sector);
        track <- tracksector >> 8;
        sector <- tracksector & 0xff;

        result <- bdio_readsec(track, sector, BDIO_TMP_SECTBUF);

        if(result = FDD_RESULT_OK)
        {
            Pentry <- (entryNo & 0x08) << 4;
            Pentry <- BDIO_TMP_SECTBUF + Pentry;

            poke8(Pentry, entryNo);
            mzero(Pentry + 1, BDIO_FCAT_ENTRY_LENGTH - 1);
            poke8(Pentry + BDIO_FCAT_ENTRYOFF_ATTRIBS, attribs);
            poke16(BDIO_VAR_FCAT_NEWENTRYADDR, Pentry);
        }
    }
    else
    {
        result <- BDIO_RESULT_ENDOFCAT;
    }

    return result;
}

byte bdio_setdrive(byte drive)
{
    // sets active drive
    // stores current active drive to BDIO_VAR_ACTIVEDRV
    // returns fdd state

    byte fdddrivecmd;
    fdddrivecmd <- FDD_CMD_SETDRVA + drive;

    FDD_PORT;
    asm "psh ci";
    fdddrivecmd;
    asm "pop cs";
    asm "mov a, ci";
    asm "out #cs, a";

    byte result;

    result <- bdio_checkstate();

    if(result = FDD_RESULT_OK)
    {
        result <- bdio_fcat_read();
        poke8(BDIO_VAR_ACTIVEDRV, drive);
    }

    return result;
}

word bdio_getfreesect()
{
    byte freetrack;
    byte freesector;
    word freetracksector;
    word nextfreetracksector;

    freetrack <- peek8(BDIO_VAR_FCAT_FREETRACK);
    freesector <- peek8(BDIO_VAR_FCAT_FREESECT);

    freetracksector <- (freetrack << 8) | freesector;
    nextfreetracksector <- bdio_tracksector_add(freetrack, freesector, 1);
    freetrack <- nextfreetracksector >> 8;
    freesector <- nextfreetracksector & 0x0f;
    
    poke8(BDIO_VAR_FCAT_FREETRACK, freetrack);
    poke8(BDIO_VAR_FCAT_FREESECT, freesector);

    return freetracksector;
}

byte bdio_new_fdesc(word Pfdesc, byte fdescNo, byte fdescMode, byte fcatNo, byte track, byte sector, byte len, byte fcattrack, byte fcatsector)
{
    fdescNo <- fdescNo | fdescMode;

    poke8(Pfdesc + BDIO_FDESCRIPTOROFF_NUMBER, fdescNo);
    poke8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRTRACK, track);
    poke8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRSECT, sector);
    poke8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRSEQ, 0x00);
    poke8(Pfdesc + BDIO_FDESCRIPTOROFF_SEQLEN, len);
    poke8(Pfdesc + BDIO_FDESCRIPTOROFF_FCATENTRYNO, fcatNo);
    poke8(Pfdesc + BDIO_FDESCRIPTOROFF_FCATTRACK, fcattrack);
    poke8(Pfdesc + BDIO_FDESCRIPTOROFF_FCATSECT, fcatsector);

    return fdescNo;
}

byte bdio_getfree_readfdesc(word PfcatEntry)
{
    word Pfdesc;
    byte fdescNo;
    byte fdescNumber;

    Pfdesc <- BDIO_VAR_FDESCTAB_READ;
    fdescNumber <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_NUMBER);
    fdescNo <- 0;

    while((fdescNo < BDIO_FDESCRIPTOR_READ_MAX) && (fdescNumber != BDIO_FDESCRIPTOR_NUMBERFREE))
    {
        Pfdesc <- Pfdesc + BDIO_FDESCRIPTOR_LEN;
        fdescNumber <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_NUMBER);
        
        fdescNo <- fdescNo + 1;
    }

    if(fdescNumber = BDIO_FDESCRIPTOR_NUMBERFREE)
    {
        byte track;
        byte sector;
        byte sectlen;
        byte fcatEntryNo;
        byte fcattrack;
        byte fcatsector;

        fcatEntryNo <- peek8(PfcatEntry + BDIO_FCAT_ENTRYOFF_NUMBER);
        track <- peek8(PfcatEntry + BDIO_FCAT_ENTRYOFF_STARTTRACK);
        sector <- peek8(PfcatEntry + BDIO_FCAT_ENTRYOFF_STARTSECTOR);
        sectlen <- peek8(PfcatEntry + BDIO_FCAT_ENTRYOFF_SECTLEN);
        fcattrack <- peek8(BDIO_VAR_FCAT_SCAN_TRACK);
        fcatsector <- peek8(BDIO_VAR_FCAT_SCAN_SECT);

        fdescNo <- bdio_new_fdesc(
            Pfdesc, 
            fdescNo, 
            BDIO_FDESCRIPTOR_NUMBERREAD, 
            fcatEntryNo, 
            track, 
            sector, 
            sectlen, 
            fcattrack, 
            fcatsector
        );
    }
    else
    {
        fdescNo <- BDIO_FDESCRIPTOR_NUMBERFULL;
    }

    return fdescNo;
}

byte bdio_fcat_checkattribs(word PfcatEntry, byte attribs)
{
    byte fcatattribs;

    fcatattribs <- peek8(PfcatEntry + BDIO_FCAT_ENTRYOFF_ATTRIBS);

    return ((fcatattribs & attribs) = attribs);
}

byte bdio_fbinopenr(word Pfnameext)
{
    //allocates file descriptor for the given file name
    //and prepares it to be read sequentially
    byte fhandle;
    byte fddres;

    fhandle <- BDIO_FOPEN_FDD_NOT_READY;
    //1. check drive state
    fddres <- bdio_checkstate();

    if(fddres = FDD_RESULT_OK)
    {
        //find file first
        word PfcatEntry;
        PfcatEntry <- bdio_ffindfile(Pfnameext);

        if(PfcatEntry != BDIO_FNAME_NOTFOUND)
        {
            fhandle <- BDIO_FOPEN_ATTR_NOREAD;

            if(bdio_fcat_checkattribs(PfcatEntry, BDIO_FILE_ATTRIB_READ))
            {
                fhandle <- bdio_getfree_readfdesc(PfcatEntry);
            }
        }
        else
        {
            fhandle <- BDIO_FOPEN_FNAME_NOTFOUND;
        }
    }

    return fhandle;
}

word bdio_getfdesc_addr(byte fhandle)
{
    word Pfdesc;
    Pfdesc <- BDIO_NULL;

    if((fhandle & BDIO_FDESCRIPTOR_NUMBERWRITE) = BDIO_FDESCRIPTOR_NUMBERWRITE)
    {
        Pfdesc <- BDIO_VAR_FDESCTAB_WRITE;
    }

    if((fhandle & BDIO_FDESCRIPTOR_NUMBERREAD) = BDIO_FDESCRIPTOR_NUMBERREAD)
    {
        Pfdesc <- BDIO_VAR_FDESCTAB_READ + ((fhandle & 0x0f) * BDIO_FDESCRIPTOR_LEN);
    }
    
    return Pfdesc;
}

byte bdio_fbinread(byte fhandle, word Pmembuf, byte sectors)
{
    //reads at most specified number of sectors for open fhandle into given Pmembuf
    //returns number of actually read sectors (EOF may be reached first)
    byte result;
    result <- 0;

    if((fhandle & BDIO_FDESCRIPTOR_NUMBERREAD) = BDIO_FDESCRIPTOR_NUMBERREAD)
    {
        word Pfdesc;
        byte sectorsread;
        byte currSeq;
        byte seqLen;
        byte track;
        byte sector;
        word tracksector;

        Pfdesc <- bdio_getfdesc_addr(fhandle);
        sectorsread <- 0;
        currSeq <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRSEQ);
        seqLen <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_SEQLEN);
        track <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRTRACK);
        sector <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRSECT);
        
        while((sectorsread < sectors) && (currSeq < seqLen))
        {
            bdio_readsec(track, sector, Pmembuf);

            Pmembuf <- Pmembuf + BDIO_SECTBUF_LEN;
            sectorsread <- sectorsread + 1;
            currSeq <- currSeq + 1;
            tracksector <- bdio_tracksector_add(track, sector, 1);
            track <- tracksector >> 8;
            sector <- tracksector & 0xff;
        }

        poke8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRSEQ, currSeq);
        poke8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRTRACK, track);
        poke8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRSECT, sector);
        result <- sectorsread;
    }

     return result;
}

byte bdio_fclose(byte fhandle)
{
    word Pfdesc;
    byte result;
    byte fdescNo;

    result <- BDIO_FCLOSE_FDESC_NOTFOUND;
    Pfdesc <- bdio_getfdesc_addr(fhandle);
    fdescNo <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_NUMBER);

    if(fdescNo != BDIO_FDESCRIPTOR_NUMBERFREE)
    {
        poke8(Pfdesc + BDIO_FDESCRIPTOROFF_NUMBER, BDIO_FDESCRIPTOR_NUMBERFREE);
        poke8(Pfdesc + BDIO_FDESCRIPTOROFF_SEQLEN, 0x00);
        result <- fdescNo;
    }
}

word bdio_freemem()
{
    //returns how much free memory we are leaving for the user
    //this is estimated value based on the difference
    //between the BDIO_USERMEM and tip of the system stack

    word Pprocstackhead;

    Pprocstackhead <- bdio_get_procstackhead();
    return (Pprocstackhead - BDIO_USERMEM);
}

word bdio_freememsect()
{
    //returns how many full fdd sectors we can fit in usermem
    return bdio_freemem() / BDIO_SECTBUF_LEN;
}

byte bdio_execute(word Pfnameext)
{
    //looks for file of given name on disk
    //if exists check if it has exec attribute
    //if so loads the file into memory (it has to be sufficient!)
    //end executes it

    byte result;
    byte fhandle;

    fhandle <- bdio_fbinopenr(Pfnameext);

    if(fhandle < 0xef)
    {
        word Pfdesc;
        byte fdescfcatEntryNo;
        byte fcatEntryNo;
        word PfcatEntry;

        Pfdesc <- bdio_getfdesc_addr(fhandle);

        if(Pfdesc != BDIO_NULL)
        {
            fdescfcatEntryNo <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_FCATENTRYNO);
            PfcatEntry <- #(BDIO_VAR_FCAT_PLASTFOUND);
            fcatEntryNo <- peek8(PfcatEntry + BDIO_FCAT_ENTRYOFF_NUMBER);
            result <- BDIO_FEXEC_FDESCFCAT_ERR;

            if(fdescfcatEntryNo = fcatEntryNo)
            {
                result <- BDIO_FEXEC_ATTR_NOEXEC;
                if(bdio_fcat_checkattribs(PfcatEntry, BDIO_FILE_ATTRIB_EXEC))
                {
                    word userspace;
                    byte filesectlen;
                    byte filesectread;

                    userspace <- bdio_freememsect();
                    filesectlen <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_SEQLEN);
                    result <- BDIO_FEXEC_OUTOFMEM;

                    if(filesectlen < userspace)
                    {
                        filesectread <- bdio_fbinread(fhandle, BDIO_USERMEM, filesectlen);
                        result <- BDIO_FEXEC_SECTFAIL;

                        if(filesectread = filesectlen)
                        {
                            //finally! program loaded we can run it!
                            //load usermem to csci
                            BDIO_USERMEM;
                            asm "cal csci";
                            result <- BDIO_FEXEC_OK;
                        }
                    }
                }
            }
        }

        bdio_fclose(fhandle);
    }
    else
    {
        result <- fhandle;
    }

    return result;
}

word bdio_call()
{
    asm "psh a";
    asm "psh cs";
    asm "psh ci";
    asm "psh ds";
    asm "psh di";
    word regA;
    word regCSCI;
    word regDSDI;
    regDSDI;
    asm "cal :dec16";
    asm "pop ci";
    asm "pop cs";
    asm "cal :poke16";
    asm "cal :printhex16";
    regCSCI;
    asm "cal :dec16";
    asm "pop ci";
    asm "pop cs";
    asm "cal :poke16";
    asm "cal :printhex16";
    regA;
    asm "cal :dec16";
    asm "pop ci";
    asm "mov cs, 0x00";
    asm "cal :poke16";
    asm "cal :printhex16";

    printf("csci %w dsdi %w a %x", regCSCI, regDSDI, regA);
    
    return 0xabba;
}
