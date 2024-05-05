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

#define BDIO_DRIVEA 0x00
#define BDIO_DRIVEB 0x01
#define BDIO_FNODETAB_STARTTRACK 0x04
#define BDIO_FNODETAB_ENDTRACK 0x05
#define BDIO_FNODE_PERSECTOR 0x10
#define BDIO_FNODE_SIZE 0x10

#define BDIO_VAR_LASTERROR 0x2f00
#define BDIO_VAR_ACTIVEDRV 0x2f01
#define BDIO_VAR_FREESECTDRV 0x2f02
#define BDIO_TAB_FREESECT 0x2f80
#define BDIO_TAB_FREESECT_LEN 0x80
#define BDIO_TMP_SECTBUF 0x0e80

byte bdio_getstate()
{
    FDD_PORT;
    asm "in a, #ci";
    asm "mov ci, a";
}

byte bdio_checkstate()
{
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
    return bdio_iosec(FDD_CMD_READ, track, sector, Pmembuf);
}

byte bdio_writesec(byte track, byte sector, word Pmembuf) 
{
    return bdio_iosec(FDD_CMD_WRITE, track, sector, Pmembuf);
}

byte bdio_getdrive()
{
    return #(BDIO_VAR_ACTIVEDRV);
}

byte bdio_fnode_freemap_refresh(byte track, byte sector)
{
    byte currFnode;
    word Pcurrfnode;
    word Pcurrtabitem;
    byte currtabitem;

    track <- track - BDIO_FNODETAB_STARTTRACK;
    currFnode <- 0;
    Pcurrtabitem <- track * BDIO_FNODE_PERSECTOR + sector;
    Pcurrtabitem <- Pcurrtabitem >> 3;
    currtabitem <- 0;

    while (currFnode < BDIO_FNODE_PERSECTOR) 
    {
        Pcurrfnode <- currFnode * BDIO_FNODE_SIZE + BDIO_TMP_SECTBUF;
 
    }
}

byte bdio_freesect_refresh()
{
    byte track;
    byte sector;
    byte result;

    track <- BDIO_FNODETAB_STARTTRACK;
    sector <- 0;
    result <- FDD_RESULT_OK;

    while (track <= BDIO_FNODETAB_ENDTRACK || result != FDD_RESULT_OK)
    {
        result <- bdio_readsec(track, sector, BDIO_TMP_SECTBUF);

        if (result = FDD_RESULT_OK)
        {
            bdio_fnode_freemap_refresh(track, sector);
        }

        sector <- sector + 1;
        if(sector > FDD_TRACKS)
        {
            track <- track + 1;
            sector <- 0;
        }
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
