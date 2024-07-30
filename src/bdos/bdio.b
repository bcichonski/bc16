#include bdioh.b

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

byte bdio_getdrive()
{
    byte drv;
    // returns active drive as os remembers
    drv <- peek8(BDIO_VAR_ACTIVEDRV);

    //printf("drv: %x%n", drv);
    return drv;
}

byte bdio_fcat_var(byte track, byte sector)
{
    poke8(BDIO_VAR_FCAT_SCAN_TRACK, track);
    poke8(BDIO_VAR_FCAT_SCAN_SECT, sector);
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
    sector <- BDIO_FCAT_STARTSECTOR;

    result <- bdio_iosec(FDD_CMD_READ, track, sector, PsectorBuf);

    if (result = FDD_RESULT_OK) 
    {
        bdio_fcat_var(track, sector);
    }

    return result;
}

byte bdio_fcat_scannext(word PsectorBuf)
{
    // method continues catalog read
    // reads next sector to PsectorBuf
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
        result <- bdio_iosec(FDD_CMD_READ, track, sector, PsectorBuf);

        if (result = FDD_RESULT_OK) 
        {
            bdio_fcat_var(track, sector);
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
    byte firstempty;

    freeentry <- peek8(BDIO_VAR_FCAT_FREEENTRY);
    freetrack <- peek8(BDIO_VAR_FCAT_FREETRACK);
    freesector <- peek8(BDIO_VAR_FCAT_FREESECT);

    freetracksector <- (freetrack << 4) | freesector;

    Pentry <- PsectorBuf;
    PlastAddr <- PsectorBuf + BDIO_SECTBUF_LEN;
    firstempty <- FALSE;

    while((Pentry < PlastAddr) && !firstempty)
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
            firstempty <- TRUE;
        }

        Pentry <- Pentry + BDIO_FCAT_ENTRY_LENGTH;
    }

    return !firstempty;
}

word bdio_fcat_ffindmem(word Pfnameext, word PsectorBuf)
{
    //looks in loaded to memory at PsectorBuf fcat sector 
    //a fcat entry with given name
    //returns BDIO_FNAME_NOTFOUND or address of the matching entry
    word Pentry;
    word PlastAddr;
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
        found <- BDIO_FNAME_EOC;

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
        if(found = TRUE)
        {
            Pentry <- Pentry - BDIO_FCAT_ENTRY_LENGTH;
        }
        else
        {
            Pentry <- BDIO_FNAME_ENDOFCAT;
        }
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
        result <- BDIO_RESULT_ENDOFCAT;
        if(bdio_fcat_scanmem(BDIO_TMP_SECTBUF))
        {
            result <- bdio_fcat_scannext(BDIO_TMP_SECTBUF);
        }
    }

    if(result = BDIO_RESULT_ENDOFCAT)
    {
        result <- FDD_RESULT_OK;
    }

    if(peek8(BDIO_VAR_FCAT_FREEENTRY) = BDIO_FCAT_FREEENTRY_FULL)
    {
        result <- BDIO_RESULT_ENDOFCAT;
    }

    //printf("free %x%x %x%n", peek8(BDIO_VAR_FCAT_FREETRACK), peek8(BDIO_VAR_FCAT_FREESECT), peek8(BDIO_VAR_FCAT_FREEENTRY));

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

    if(result = BDIO_FNAME_ENDOFCAT)
    {
        result <- BDIO_FNAME_NOTFOUND;
    }

    poke16(BDIO_VAR_FCAT_PLASTFOUND, result);
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

byte bdio_new_fcat(word Pfnameext, byte attribs)
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
    byte ftrack;
    byte fsector;
    word tracksector;
    word Pentry;

    result <- BDIO_RESULT_ENDOFCAT;
    entryNo <- peek8(BDIO_VAR_FCAT_FREEENTRY);

    if(entryNo != BDIO_FCAT_FREEENTRY_FULL)
    {
        sector <- entryNo >> 3;
        tracksector <- bdio_tracksector_add(BDIO_FCAT_STARTTRACK, BDIO_FCAT_STARTSECTOR, sector);
        track <- tracksector >> 8;
        sector <- tracksector & 0xff;

        result <- bdio_iosec(FDD_CMD_READ, track, sector, BDIO_TMP_SECTBUF);

        if(result = FDD_RESULT_OK)
        {
            tracksector <- bdio_getfreesect();
            ftrack <- tracksector >> 8;
            fsector <- tracksector & 0xff; 

            Pentry <- (entryNo & 0x07) << 4;
            Pentry <- BDIO_TMP_SECTBUF + Pentry;

            mzero(Pentry, BDIO_FCAT_ENTRY_LENGTH);

            poke8(Pentry + BDIO_FCAT_ENTRYOFF_NUMBER, entryNo);
            poke8(Pentry + BDIO_FCAT_ENTRYOFF_STARTTRACK, ftrack);
            poke8(Pentry + BDIO_FCAT_ENTRYOFF_STARTSECTOR, fsector);
            poke8(Pentry + BDIO_FCAT_ENTRYOFF_SECTLEN, 0x01);

            attribs <- attribs | BDIO_FILE_ATTRIB_WRITE;
            poke8(Pentry + BDIO_FCAT_ENTRYOFF_ATTRIBS, attribs);
            strncpy(Pfnameext, Pentry + BDIO_FCAT_ENTRYOFF_FNAME, BDIO_FCAT_ENTRY_NAMELEN);

            poke16(BDIO_VAR_FCAT_NEWENTRYADDR, Pentry);
            poke8(BDIO_VAR_FCAT_FREEENTRY, entryNo + 1);
            bdio_fcat_var(track, sector);
        }
    }

    return result;
}

byte bdio_setdrive(byte drive, byte silent)
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

    if((!silent) && (result = FDD_RESULT_OK))
    {
        result <- bdio_fcat_read();
        poke8(BDIO_VAR_ACTIVEDRV, drive);
    }

    return result;
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

byte bdio_getfree_fdesc_internal(word PfcatEntry, word Pfdesc, byte maxfdesc)
{
    byte fdescNo;
    byte fdescNumber;

    fdescNumber <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_NUMBER);
    fdescNo <- 0;

    while((fdescNo < maxfdesc) && (fdescNumber != BDIO_FDESCRIPTOR_NUMBERFREE))
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
        byte fdescMode;
        word tracksector;

        fcatEntryNo <- peek8(PfcatEntry + BDIO_FCAT_ENTRYOFF_NUMBER);
        fcattrack <- peek8(BDIO_VAR_FCAT_SCAN_TRACK);
        fcatsector <- peek8(BDIO_VAR_FCAT_SCAN_SECT);
        track <- peek8(PfcatEntry + BDIO_FCAT_ENTRYOFF_STARTTRACK);
        sector <- peek8(PfcatEntry + BDIO_FCAT_ENTRYOFF_STARTSECTOR);

        if(Pfdesc = BDIO_VAR_FDESCTAB_WRITE)
        {
            fdescMode <- BDIO_FDESCRIPTOR_NUMBERWRITE;
            sectlen <- 0x00;
        }
        else
        {
            fdescMode <- BDIO_FDESCRIPTOR_NUMBERREAD;
            sectlen <- peek8(PfcatEntry + BDIO_FCAT_ENTRYOFF_SECTLEN);
        }

        fdescNumber <- bdio_new_fdesc(
            Pfdesc, 
            fdescNo, 
            fdescMode, 
            fcatEntryNo, 
            track, 
            sector, 
            sectlen, 
            fcattrack, 
            fcatsector
        );
        fdescNo <- fdescNumber;
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

    return (fcatattribs & attribs);
}

byte bdio_fbinopen_internal(word Pfnameext, byte testattrib)
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
        fhandle <- BDIO_FOPEN_FNAME_NOTFOUND;
        PfcatEntry <- bdio_ffindfile(Pfnameext);

        if(PfcatEntry != BDIO_FNAME_NOTFOUND)
        {
            fhandle <- testattrib;
            if(testattrib = BDIO_FOPEN_ATTR_NOREAD)
            {
                if(bdio_fcat_checkattribs(PfcatEntry, BDIO_FILE_ATTRIB_READ))
                {
                    fhandle <- bdio_getfree_fdesc_internal(PfcatEntry, BDIO_VAR_FDESCTAB_READ, BDIO_FDESCRIPTOR_READ_MAX);
                }
            }
            else
            {
                if(bdio_fcat_checkattribs(PfcatEntry, BDIO_FILE_ATTRIB_WRITE))
                {
                    fhandle <- bdio_getfree_fdesc_internal(PfcatEntry, BDIO_VAR_FDESCTAB_WRITE, BDIO_FDESCRIPTOR_WRITE_MAX);
                }
            }
        }
    }

    return fhandle;
}

word bdio_getfdesc_addr(byte fhandle)
{
    word Pfdesc;
    Pfdesc <- BDIO_NULL;

    if(fhandle & BDIO_FDESCRIPTOR_NUMBERWRITE)
    {
        Pfdesc <- BDIO_VAR_FDESCTAB_WRITE;
    }

    if(fhandle & BDIO_FDESCRIPTOR_NUMBERREAD)
    {
        Pfdesc <- BDIO_VAR_FDESCTAB_READ + ((fhandle & 0x0f) * BDIO_FDESCRIPTOR_LEN);
    }
    
    return Pfdesc;
}

byte bdio_fbin_internal(byte fhandle, word Pmembuf, byte sectors, byte descMode)
{
    //reads at most specified number of sectors for open fhandle into given Pmembuf
    //returns number of actually read sectors (EOF may be reached first)
    byte result;
    result <- 0;

    if(fhandle & descMode)
    {
        word Pfdesc;
        byte sectorscount;
        byte currSeq;
        byte seqLen;
        byte track;
        byte sector;
        word tracksector;

        Pfdesc <- bdio_getfdesc_addr(fhandle);
        sectorscount <- 0;
        currSeq <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRSEQ);
        seqLen <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_SEQLEN);
        track <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRTRACK);
        sector <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRSECT);
        
        while((sectorscount < sectors) && ((descMode = BDIO_FDESCRIPTOR_NUMBERWRITE) || (currSeq < seqLen)))
        {
            if(descMode = BDIO_FDESCRIPTOR_NUMBERREAD)
            {
                bdio_iosec(FDD_CMD_READ, track, sector, Pmembuf);
                tracksector <- bdio_tracksector_add(track, sector, 1);
            }
            else
            {
                bdio_iosec(FDD_CMD_WRITE, track, sector, Pmembuf);
                tracksector <- bdio_getfreesect();             
            }

            Pmembuf <- Pmembuf + BDIO_SECTBUF_LEN;
            sectorscount <- sectorscount + 1;
            currSeq <- currSeq + 1;
            
            track <- tracksector >> 8;
            sector <- tracksector & 0xff;

            if(currSeq & 0x0008)
            {
                puts(".");
            }
        }

        poke8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRSEQ, currSeq);
        poke8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRTRACK, track);
        poke8(Pfdesc + BDIO_FDESCRIPTOROFF_CURRSECT, sector);

        if(descMode != BDIO_FDESCRIPTOR_NUMBERREAD)
        {
            poke8(Pfdesc + BDIO_FDESCRIPTOROFF_SEQLEN, currSeq);   
        }
        
        result <- sectorscount;
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

    //printf("fclose: %x%n", fhandle);

    if(fdescNo != BDIO_FDESCRIPTOR_NUMBERFREE)
    {
        result <- fdescNo;

        if(fhandle & BDIO_FDESCRIPTOR_NUMBERWRITE)
        {
            //we need to update fcat entry based on fdesc
            byte fcatNo;
            byte fcattrack;
            byte fcatsector;
            byte fcatseclen;
            word PfcatEntry;

            fcatNo <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_FCATENTRYNO);
            fcattrack <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_FCATTRACK);
            fcatsector <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_FCATSECT);
            fcatseclen <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_SEQLEN);

            result <- bdio_iosec(FDD_CMD_READ, fcattrack, fcatsector, BDIO_TMP_SECTBUF);

            if(result = FDD_RESULT_OK)
            {
                bdio_fcat_var(fcattrack, fcatsector);
                PfcatEntry <- (fcatNo & 0x07) << 4;
                PfcatEntry <- BDIO_TMP_SECTBUF + PfcatEntry;

                poke8(PfcatEntry + BDIO_FCAT_ENTRYOFF_SECTLEN, fcatseclen);

                result <- bdio_iosec(FDD_CMD_WRITE, fcattrack, fcatsector, BDIO_TMP_SECTBUF);
                if(result = FDD_RESULT_OK)
                {
                    result <- fdescNo;
                }
                else
                {
                    result <- BDIO_FCLOSE_FCAT_SAVEERR;
                }
            }
            else
            {
                result <- BDIO_FCLOSE_FCAT_READERR;
            }
        }

        poke8(Pfdesc + BDIO_FDESCRIPTOROFF_NUMBER, BDIO_FDESCRIPTOR_NUMBERFREE);
        poke8(Pfdesc + BDIO_FDESCRIPTOROFF_SEQLEN, 0x00);
    }

    return result;
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

byte bdio_execute(word Pfnameext)
{
    //looks for file of given name on disk
    //if exists check if it has exec attribute
    //if so loads the file into memory (it has to be sufficient!)
    //end executes it

    byte result;
    byte fhandle;

    fhandle <- bdio_fbinopen_internal(Pfnameext, BDIO_FOPEN_ATTR_NOREAD);

    if(fhandle < BDIO_FOPEN_FNAME_NOTFOUND)
    {
        word Pfdesc;
        byte fdescfcatEntryNo;
        byte fcatEntryNo;
        word PfcatEntry;
        byte fclosed;

        fclosed <- FALSE;
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

                    userspace <- bdio_freemem() / BDIO_SECTBUF_LEN;
                    filesectlen <- peek8(Pfdesc + BDIO_FDESCRIPTOROFF_SEQLEN);
                    result <- BDIO_FEXEC_OUTOFMEM;

                    if(filesectlen < userspace)
                    {
                        filesectread <- bdio_fbin_internal(fhandle, BDIO_USERMEM, filesectlen, BDIO_FDESCRIPTOR_NUMBERREAD);
                        result <- BDIO_FEXEC_SECTFAIL;

                        if(filesectread = filesectlen)
                        {
                            bdio_fclose(fhandle);
                            fclosed <- TRUE;
                            putnl();

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

        if(!fclosed)
        {
            bdio_fclose(fhandle);
        }
    }
    else
    {
        result <- fhandle;
    }

    return result;
}

byte bdio_finternal(word Pfnameext, byte mode, byte attribs)
{
    word PfcatEntry;
    byte fhandle;
    byte fddres;
    byte fcattrack;
    byte fcatsector;

    fhandle <- BDIO_FILE_FDD_NOT_READY;
    //1. check drive state
    fddres <- bdio_checkstate();

    if(fddres = FDD_RESULT_OK)
    {
        //find file first
        PfcatEntry <- bdio_ffindfile(Pfnameext);
        fhandle <- BDIO_FILE_FNAME_NOTFOUND;

        if(PfcatEntry != BDIO_FNAME_NOTFOUND)
        {
            fhandle <- BDIO_FILE_SAVEERR;

            if(mode = BDIO_FILE_INTERNALMODE_DELETE)
            {
                poke8(PfcatEntry + BDIO_FCAT_ENTRYOFF_SECTLEN, 0x00);
            }
            else
            {
                if(mode = BDIO_FILE_INTERNALMODE_SETATTR)
                {
                    poke8(PfcatEntry + BDIO_FCAT_ENTRYOFF_ATTRIBS, attribs);
                }
            }

            fddres <- bdio_iosec(FDD_CMD_WRITE, fcattrack, fcatsector, BDIO_TMP_SECTBUF);

            if(fddres = FDD_RESULT_OK)
            {
                fhandle <- BDIO_FILE_OK;
            }
        }
    }

    return fhandle;
}

byte bdio_fcreate(word Pfnameext, byte attribs)
{
    word PfcatEntry;
    byte fhandle;
    byte fddres;
    byte fcattrack;
    byte fcatsector;

    fhandle <- BDIO_FCREATE_FDD_NOT_READY;
    //1. check drive state
    fddres <- bdio_checkstate();

    if(fddres = FDD_RESULT_OK)
    {
        //find file first
        PfcatEntry <- bdio_ffindfile(Pfnameext);
        fhandle <- BDIO_FCREATE_FNAME_FOUND;

        if(PfcatEntry = BDIO_FNAME_NOTFOUND)
        {
            fddres <- bdio_new_fcat(Pfnameext, attribs);
            fhandle <- BDIO_FCREATE_READERR;

            if(fddres = FDD_RESULT_OK)
            {
                fcattrack <- peek8(BDIO_VAR_FCAT_SCAN_TRACK);
                fcatsector <- peek8(BDIO_VAR_FCAT_SCAN_SECT);

                fhandle <- BDIO_FCREATE_SAVEERR;
                fddres <- bdio_iosec(FDD_CMD_WRITE, fcattrack, fcatsector, BDIO_TMP_SECTBUF);

                if(fddres = FDD_RESULT_OK)
                {
                    fhandle <- BDIO_FCREATE_OK;
                }
            }
        }
    }

    return fhandle;
}

word bdio_call()
{
    asm "bdio_call: psh a";
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
    regCSCI;
    asm "cal :dec16";
    asm "pop ci";
    asm "pop cs";
    asm "cal :poke16";
    regA;
    asm "cal :dec16";
    asm "pop ci";
    asm "mov cs, 0x00";
    asm "cal :poke16";

    word result;
    result <- BDIO_NULL;
    byte regCS;
    byte regDS;
    byte regCI;

    if(regA = BDIO_FBINOPENR)
    {
        result <- bdio_fbinopen_internal(regCSCI, BDIO_FOPEN_ATTR_NOREAD);
    }

    if(regA = BDIO_FBINOPENW)
    {
        result <- bdio_fbinopen_internal(regCSCI, BDIO_FOPEN_ATTR_NOWRITE);
    }

    regDS <- regDSDI >> 8;

    if(regA = BDIO_FCREATE)
    {
        result <- bdio_fcreate(regCSCI, regDS);
    }

    if(regA = BDIO_FDELETE)
    {
        result <- bdio_finternal(regCSCI, BDIO_FILE_INTERNALMODE_DELETE, 0x00);
    }
    
    if(regA = BDIO_FSETATTR)
    {
        result <- bdio_finternal(regCSCI, BDIO_FILE_INTERNALMODE_SETATTR, regDS);
    }

    regCS <- regCSCI >> 8;
    regCI <- regCSCI & 0x00ff;

    if(regA = BDIO_FBINREAD)
    {
        result <- bdio_fbin_internal(regCS, regDSDI, regCI, BDIO_FDESCRIPTOR_NUMBERREAD);
    }

    if(regA = BDIO_FBINWRITE)
    {
        result <- bdio_fbin_internal(regCS, regDSDI, regCI, BDIO_FDESCRIPTOR_NUMBERWRITE);
    }
    
    if(regA = BDIO_FCLOSE)
    {
        result <- bdio_fclose(regCI);
    }
    
    if(regA = BDIO_SETDRIVE)
    {
        result <- bdio_setdrive(regCS, regDS);
    }

    if(regA = BDIO_GETDRIVE)
    {
        result <- bdio_getdrive();
    }

    if(regA = BDIO_READSECTOR)
    {
        result <- bdio_iosec(FDD_CMD_READ, regCS, regCI, regDSDI);
    }

    if(regA = BDIO_WRITESECTOR)
    {
        result <- bdio_iosec(FDD_CMD_WRITE, regCS, regCI, regDSDI);
    }

    return result;
}
