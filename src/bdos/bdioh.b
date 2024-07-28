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
#define BDIO_FCAT_STARTTRACK 0x00
#define BDIO_FCAT_STARTSECTOR 0x01
#define BDIO_FCAT_ENDTRACK 0x01
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
#define BDIO_FNAME_ENDOFCAT 0x0001
#define BDIO_FNAME_EOC 0xff

#define BDIO_FDESCRIPTOROFF_NUMBER 0x00
#define BDIO_FDESCRIPTOROFF_FCATENTRYNO 0x01
#define BDIO_FDESCRIPTOROFF_CURRTRACK 0x02
#define BDIO_FDESCRIPTOROFF_CURRSECT 0x03
#define BDIO_FDESCRIPTOROFF_CURRSEQ 0x04
#define BDIO_FDESCRIPTOROFF_SEQLEN 0x05
#define BDIO_FDESCRIPTOROFF_FCATTRACK 0x06
#define BDIO_FDESCRIPTOROFF_FCATSECT 0x07
#define BDIO_FDESCRIPTOR_READ_MAX 0x03
#define BDIO_FDESCRIPTOR_WRITE_MAX 0x00
#define BDIO_FDESCRIPTOR_LEN 0x08
#define BDIO_FDESCRIPTOR_NUMBERFREE 0x00
#define BDIO_FDESCRIPTOR_NUMBERWRITE 0x10
#define BDIO_FDESCRIPTOR_NUMBERREAD 0x20
#define BDIO_FDESCRIPTOR_NUMBERFULL 0xff

#define BDIO_FOPEN_FNAME_NOTFOUND 0xe0
#define BDIO_FOPEN_FDD_NOT_READY 0xe1
#define BDIO_FOPEN_ATTR_NOREAD 0xe3
#define BDIO_FOPEN_ATTR_NOWRITE 0xe4
#define BDIO_FOPEN_FDD_NOT_READY 0xe5

#define BDIO_FCREATE_FNAME_EXISTS 0xe6
#define BDIO_FCREATE_READERR 0xeb
#define BDIO_FCREATE_SAVEERR 0xec
#define BDIO_FCREATE_FDD_NOT_READY 0xed
#define BDIO_FCREATE_FNAME_FOUND 0xee
#define BDIO_FCREATE_OK 0x00

#define BDIO_FILE_SAVEERR 0xf0
#define BDIO_FILE_FDD_NOT_READY 0xf1
#define BDIO_FILE_FNAME_NOTFOUND 0xf2
#define BDIO_FILE_OK 0x00

#define BDIO_FILE_INTERNALMODE_DELETE 0xd0
#define BDIO_FILE_INTERNALMODE_SETATTR 0x5a

#define BDIO_FCLOSE_FDESC_NOTFOUND 0xe2
#define BDIO_FCLOSE_FCAT_READERR 0xe6
#define BDIO_FCLOSE_FCAT_SAVEERR 0xe7

#define BDIO_FEXEC_ATTR_NOEXEC 0xe7
#define BDIO_FEXEC_FDESCFCAT_ERR 0xe8
#define BDIO_FEXEC_OUTOFMEM 0xe9
#define BDIO_FEXEC_SECTFAIL 0xea
#define BDIO_FEXEC_OK 0x00

#define BDIO_FILE_ATTRIB_READ 0x01
#define BDIO_FILE_ATTRIB_WRITE 0x02
#define BDIO_FILE_ATTRIB_EXEC 0x04
#define BDIO_FILE_ATTRIB_SYSTEM 0x80

#define BDIO_VAR_LASTERROR 0x4f00
#define BDIO_VAR_ACTIVEDRV 0x4f01
#define BDIO_VAR_FCAT_SCAN_TRACK 0x4f02
#define BDIO_VAR_FCAT_SCAN_SECT 0x4f03
#define BDIO_VAR_FCAT_FREEENTRY 0x4f04
#define BDIO_VAR_FCAT_FREETRACK 0x4f05
#define BDIO_VAR_FCAT_FREESECT 0x4f06
#define BDIO_VAR_FCAT_PLASTFOUND 0x4f08
#define BDIO_VAR_FCAT_NEWENTRYADDR 0x4f10
#define BDIO_VAR_FDESCTAB_WRITE 0x4f12
#define BDIO_VAR_FDESCTAB_READ 0x4f1a

#define BDIO_CMDPROMPTADDR 0x4fc0
#define BDIO_CMDPROMPTLEN 0x40
#define BDIO_TMP_SECTBUF 0x0e80
#define BDIO_TAB_SCANSECTBUF 0x4e80
#define BDIO_SECTBUF_LEN 0x80

#define BDIO_USERMEM 0x5000
#define BDIO_NULL 0x0000

#define BDIO_READSECTOR 0x00
#define BDIO_WRITESECTOR 0x01
#define BDIO_SETDRIVE 0x02
#define BDIO_GETDRIVE 0x03
#define BDIO_FBINOPENR 0x10
#define BDIO_FBINOPENW 0x11
#define BDIO_FBINREAD 0x12
#define BDIO_FBINWRITE 0x13
#define BDIO_FCREATE 0x14
#define BDIO_FCLOSE 0x15
#define BDIO_FDELETE 0x16
#define BDIO_FSETATTR 0x17

#include stdio.b

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

byte bdio_printexecres(byte execres)
{
    word errorMessage;
    errorMessage <- "unknown error";
    
    if(execres = BDIO_FOPEN_FDD_NOT_READY)
    {
        errorMessage <- "fdd not ready";
    }
    if(execres = BDIO_FOPEN_ATTR_NOREAD)
    {
        errorMessage <- "reading not allowed";
    }
    if(execres = BDIO_FOPEN_FNAME_NOTFOUND)
    {
        errorMessage <- "file not found";
    }
    if(execres = BDIO_FEXEC_ATTR_NOEXEC)
    {
        errorMessage <- "execution not allowed";
    }
    if(execres = BDIO_FEXEC_FDESCFCAT_ERR)
    {
        errorMessage <- "cat and file handle mismatch";
    }
    if(execres = BDIO_FEXEC_OUTOFMEM)
    {
        errorMessage <- "not enough user memory";
    }
    if(execres = BDIO_FEXEC_SECTFAIL)
    {
        errorMessage <- "not all sectors loaded";
    }

    printf("error: %x %s%n", execres, errorMessage);
}