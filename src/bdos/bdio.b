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
#define BDIO_FCAT_STARTTRACK 0x04
#define BDIO_FCAT_ENDTRACK 0x05
#define BDIO_FCAT_ENTRYOFF_NUMBER 0x00
#define BDIO_FCAT_ENTRYOFF_STARTTRACK 0x01
#define BDIO_FCAT_ENTRYOFF_STARTSECTOR 0x02
#define BDIO_FCAT_ENTRYOFF_SECTLEN 0x03
#define BDIO_FCAT_ENTRYOFF_FNAME 0x04
#define BDIO_FCAT_ENTRY_LENGTH 0x10
#define BDIO_FCAT_FREEENTRY_FULL 0xff

#define BDIO_FREEMAP_FULL 0x0000

#define BDIO_VAR_LASTERROR 0x2f00
#define BDIO_VAR_ACTIVEDRV 0x2f01
#define BDIO_VAR_FCAT_SCAN_TRACK 0x2f02
#define BDIO_VAR_FCAT_SCAN_SECT 0x2f03
#define BDIO_VAR_FCAT_FREEENTRY 0x2f04
#define BDIO_VAR_FCAT_FREETRACK 0x2f05
#define BDIO_VAR_FCAT_FREESECT 0x2f06
#define BDIO_VAR_FCAT_NEWENTRYADDR 0x2f08
#define BDIO_TAB_FREESECT_ADDR 0x2f80
#define BDIO_TAB_FREESECT_LEN 0x80
#define BDIO_TMP_SECTBUF 0x0e80
#define BDIO_TMP_SECTBUF_LEN 0x80

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
    asm "pop di";
    asm "mov a, ci";
    asm "out #ci, a";

    byte result;

    result <- bdio_checkstate();

    if(result = FDD_RESULT_OK)
    {
        poke8(BDIO_VAR_ACTIVEDRV, drive);
    }

    return result;
}

byte bdio_iosec(byte fddcmd, byte track, byte sector, word Pmembuf) 
{
    //low level function to configure dma and read or write sector there
    //returns fdd state

    byte result;
    result <- bdio_configure(Pmembuf);

    if (result = FDD_RESULT_OK)
    {
        track;
        asm "psh ci";
        sector;
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

    return bdio_iosec(FDD_CMD_READ, track, sector, Pmembuf);
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
    return #(BDIO_VAR_ACTIVEDRV);
}

byte bdio_fcat_scanfirst()
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

    result <- bdio_readsec(track, sector, BDIO_TMP_SECTBUF);

    if (result = FDD_RESULT_OK) 
    {
        poke16(BDIO_VAR_FCAT_SCAN_TRACK, track);
        poke16(BDIO_VAR_FCAT_SCAN_SECT, sector);
    }

    return result;
}

byte bdio_fcat_scannext()
{
    // method continues catalog read
    // reads next sector to BDIO_TMP_SECTBUF
    // stores current track and sector in BDIO_VAR_FCAT_SCAN_TRACK and BDIO_VAR_FCAT_SCAN_SECT
    // returns fdd state or BDIO_RESULT_ENDOFCAT

    byte track;
    byte sector;
    byte result;

    track <- #(BDIO_VAR_FCAT_SCAN_TRACK);
    sector <- #(BDIO_VAR_FCAT_SCAN_SECT);
    result <- FDD_RESULT_OK;

    sector <- sector + 1;
    if (sector >= FDD_SECTORS)
    {
        track <- track + 1;
        sector <- 0;

        if(track >= BDIO_FCAT_ENDTRACK)
        {
            result <- BDIO_RESULT_ENDOFCAT;
        }
    }

    if(result = FDD_RESULT_OK)
    {
        result <- bdio_readsec(track, sector, BDIO_TMP_SECTBUF);

        if (result = FDD_RESULT_OK) 
        {
            poke16(BDIO_VAR_FCAT_SCAN_TRACK, track);
            poke16(BDIO_VAR_FCAT_SCAN_SECT, sector);
        }
    }

    return result;
}

word bdio_tracksector_get(byte track, byte sector)
{
    return (track << 3) | sector;
}

word bdio_tracksector_add(byte track, byte sector, byte sectorlen)
{
    //calculates track sector that is a result of adding sectorlen sectors to given track/sector
    //returns word value in which first byte is track, second is sector
    word result;
    word sectors;

    sectors <- (track << 3) | sector;
    sectors <- sectors + sectorlen - 1;
    
    result <- (sectors >> 3) << 8;
    result <- result | (sectors & 0x0f);

    return result;
}

byte bdio_fcat_scanmem()
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

    freeentry <- #(BDIO_VAR_FCAT_FREEENTRY);
    freetrack <- #(BDIO_VAR_FCAT_FREETRACK);
    freesector <- #(BDIO_VAR_FCAT_FREESECT);

    freetracksector <- bdio_tracksector_get(freetrack, freesector);

    Pentry <- BDIO_TMP_SECTBUF;
    PlastAddr <- BDIO_TMP_SECTBUF + BDIO_TMP_SECTBUF_LEN;
    while(Pentry < PlastAddr)
    {
        currsectlen <- #(Pentry + BDIO_FCAT_ENTRYOFF_SECTLEN);
        currentry <- #(Pentry + BDIO_FCAT_ENTRYOFF_NUMBER);

        if(currsectlen > 0)
        {
            
            currtrack <- #(Pentry + BDIO_FCAT_ENTRYOFF_STARTTRACK);
            currsector <- #(Pentry + BDIO_FCAT_ENTRYOFF_STARTSECTOR);

            currfreetracksector <- bdio_tracksector_add(currtrack, currsector, currsectlen + 1);
            currtrack <- freetracksector >> 8;
            currsector <- freetracksector & 0x0f;

            if (freetracksector < currfreetracksector)
            {
                freetracksector <- currfreetracksector;
                poke16(BDIO_VAR_FCAT_FREETRACK, currtrack);
                poke16(BDIO_VAR_FCAT_FREESECT, currsector);
            }
        }
        else
        {
            if (currentry < freeentry)
            {
                freeentry <- currentry;
                poke16(BDIO_VAR_FCAT_FREEENTRY, freeentry);
            }
        }

        Pentry <- Pentry + BDIO_FCAT_ENTRY_LENGTH;
    }
}

byte bdio_fcat_read()
{
    //reads file catalog
    //initializes variables BDIO_VAR_FCAT_FREEENTRY, BDIO_VAR_FCAT_FREETRACK, BDIO_VAR_FCAT_FREESECT

    byte result;

    poke16(BDIO_VAR_FCAT_FREEENTRY, BDIO_FCAT_FREEENTRY_FULL);
    poke16(BDIO_VAR_FCAT_FREETRACK, 0x00);
    poke16(BDIO_VAR_FCAT_FREESECT, 0x00);

    result <- bdio_fcat_scanfirst();

    while(result = FDD_RESULT_OK)
    {
        bdio_fcat_scanmem();

        result <- bdio_fcat_scannext();
    }

    if(result = BDIO_RESULT_ENDOFCAT)
    {
        result <- FDD_RESULT_OK;
    }

    if(#(BDIO_VAR_FCAT_FREEENTRY) = BDIO_FCAT_FREEENTRY_FULL)
    {
        result <- BDIO_RESULT_ENDOFCAT;
    }

    return result;
}

byte bdio_fcat_new()
{
    //creates a new entry in fcat table
    //memory address of that entry is BDIO_VAR_FCAT_NEWENTRYADDR
    //track and sector in which this entry resides is taken from BDIO_VAR_FCAT_FREETRACK and BDIO_VAR_FCAT_FREESECT
    //initializes entry with the start track and sector
    //returns fdd state

    byte result;
    byte entryNo;

    result <- FDD_RESULT_OK;
    entryNo <- #(BDIO_VAR_FCAT_FREEENTRY);

    if(entryNo != BDIO_FCAT_FREEENTRY_FULL)
    {
        poke8(BDIO_VAR_FCAT_NEWENTRYADDR, entryNo);
        mzero(BDIO_VAR_FCAT_NEWENTRYADDR + 1, BDIO_FCAT_ENTRY_LENGTH - 1);
    }
    else
    {
        result <- BDIO_RESULT_ENDOFCAT;
    }

    return result;
}

byte bdio_call()
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
}
