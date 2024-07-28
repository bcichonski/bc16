#code 0x5000
#heap 0x7000

#include std.b
#include bdosh.b
#include strings.b

#define FILEBUFSECT_ADDR 0x7500
#define FILEBUFSECT_LEN 0x10
#define INFILEBDIONAME_ADDR 0x74f0
#define OUTFILEBDIONAME_ADDR 0x74e0
#define DRIVEPRESENT 0x0100

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

    currentDrive <- bdio_getdrive();
    currentDrive <- changeDriveIfNeeded(currentDrive, sourcedrive, FALSE);

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
                sectorsread <- bdio_fbinread(fHandleIn, FILEBUFSECT_ADDR, FILEBUFSECT_LEN);
                result <- 1;

                while(sectorsread && result)
                {
                    currentDrive <- changeDriveIfNeeded(currentDrive, targetdrive, TRUE);

                    result <- bdio_fbinwrite(fHandleOut, FILEBUFSECT_ADDR, sectorsread);

                    if(result)
                    {
                        currentDrive <- changeDriveIfNeeded(currentDrive, targetdrive, TRUE);
                        sectorsread <- bdio_fbinread(fHandleIn, FILEBUFSECT_ADDR, FILEBUFSECT_LEN);
                    }
                    else
                    {
                        printf("error writing sectors%n");
                    }
                }

                bdio_fclose(fHandleOut);
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

        bdio_fclose(fHandleIn);
    }
    else
    {
        bdio_printexecres(fHandleIn);
    }
}

byte fnormalize(word Pfilenameext, word Pbdiofilename)
{
    byte length;

    mfill(Pbdiofilename, BDIO_FCAT_ENTRY_NAMELEN, 0x20);
    poke8(Pbdiofilename + BDIO_FCAT_ENTRY_NAMELEN, NULLCHAR);

    length <- strnlen8(Pfilenameext, BDIO_FCAT_ENTRY_NAMELEN + 1);
    strncpy(Pfilenameext + length - 3, Pbdiofilename + BDIO_FCAT_ENTRY_NAMELEN - 3, 3);

    length <- strnposc(Pfilenameext, '.', BDIO_FCAT_ENTRY_NAMELEN);
    strncpy(Pfilenameext, Pbdiofilename, length);
}

byte main()
{
    word Pargs;
    word result;
    word PsrcFileNameExt;
    word PtgtFileNameExt;
    byte sourcedrv;
    byte targetdrv;
    byte len;

    upstring(BDIO_CMDPROMPTADDR);
    Pargs <- strnextword(BDIO_CMDPROMPTADDR);

    if(strncmp(Pargs, "-H", 3) = STRCMP_EQ)
    {
        printf("%s%n%s%n%s%n",
            "copy file",
            "[d:]srcfname.ext", 
            "[d:]dstfname.ext");
    }
    else
    {
        result <- getdrive(Pargs);
        poke8(Pargs - 1, NULLCHAR);
        if(result & DRIVEPRESENT)
        {
            Pargs <- Pargs + 2;  
        }

        PsrcFileNameExt <- Pargs;
        sourcedrv <- result;

        Pargs <- strnextword(Pargs);
        poke8(Pargs - 1, NULLCHAR);
        result <- getdrive(Pargs);
        if(result & DRIVEPRESENT)
        {
            Pargs <- Pargs + 2;  
        }

        PtgtFileNameExt <- Pargs;
        targetdrv <- result;

        fnormalize(PsrcFileNameExt, INFILEBDIONAME_ADDR);
        fnormalize(PtgtFileNameExt, OUTFILEBDIONAME_ADDR);

        copy(sourcedrv, INFILEBDIONAME_ADDR, targetdrv, OUTFILEBDIONAME_ADDR);
    }
}