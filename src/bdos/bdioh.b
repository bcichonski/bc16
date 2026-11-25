#include bdioh.h
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
    if(execres = BDIO_FCLOSE_FCAT_SAVEERR)
    {
        errorMessage <- "cat save error";
    }
    if(execres = BDIO_FILE_DISC_FULL)
    {
        errorMessage <- "disc full";
    }

    printf("error: %x %s%n", execres, errorMessage);
}