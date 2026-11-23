#code 0x6000
#heap 0xf000

#include std.b
#include bdosh.b
#include strings.b
#include bdostools.b
#include bdosargs.b

#define FILEBUFSECT_ADDR 0xa000
#define FILEBUFSECT_LEN 0x40
#define INFILEBDIONAME_ADDR 0xf0f0
#define OUTFILEBDIONAME_ADDR 0xf0e0

byte copy(byte sourcedrive, word Psourcefileext, byte targetdrive, word Ptargetfileext)
{
    byte currentDrive;
    byte fHandleIn;
    byte fHandleOut;
    byte sectorsread;
    byte fAttribsIn;
    byte result;
    word Pfcatentry;
    byte nowritemask;

    nowritemask <- BDIO_FILE_ATTRIB_EXEC | BDIO_FILE_ATTRIB_SYSTEM | BDIO_FILE_ATTRIB_READ;
    currentDrive <- bdio_getdrive();
    currentDrive <- changeDriveIfNeeded(currentDrive, sourcedrive, FALSE);

    fHandleIn <- bdio_fbinopenr(Psourcefileext, BDIO_FOPEN_MODE_SECTOR);
    if(fHandleIn < BDIO_FOPEN_FNAME_NOTFOUND)
    {
        Pfcatentry <- #(BDIO_VAR_FCAT_PLASTFOUND);
        fAttribsIn <- peek8(Pfcatentry + BDIO_FCAT_ENTRYOFF_ATTRIBS);
       
        currentDrive <- changeDriveIfNeeded(currentDrive, targetdrive, FALSE);

        result <- bdio_fcreate(Ptargetfileext, fAttribsIn);
        if(!result)
        {
            fHandleOut <- bdio_fbinopenw(Ptargetfileext, BDIO_FOPEN_MODE_SECTOR);

            if(fHandleOut < BDIO_FOPEN_FNAME_NOTFOUND)
            {
                currentDrive <- changeDriveIfNeeded(currentDrive, sourcedrive, TRUE);
                sectorsread <- bdio_fbinread(fHandleIn, FILEBUFSECT_ADDR, FILEBUFSECT_LEN);
                result <- 1;

                while(sectorsread && result)
                {
                    currentDrive <- changeDriveIfNeeded(currentDrive, targetdrive, TRUE);

                    result <- bdio_fbinwrite(fHandleOut, FILEBUFSECT_ADDR, sectorsread);

                    if(result)
                    {
                        currentDrive <- changeDriveIfNeeded(currentDrive, sourcedrive, TRUE);
                        sectorsread <- bdio_fbinread(fHandleIn, FILEBUFSECT_ADDR, FILEBUFSECT_LEN);
                    }
                    else
                    {
                        printf("error writing sectors%n");
                    }
                }

                currentDrive <- changeDriveIfNeeded(currentDrive, targetdrive, TRUE);
                bdio_fclose(fHandleOut);

                fAttribsIn <- fAttribsIn & nowritemask;
                bdio_fsetattr(Ptargetfileext, fAttribsIn);
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

        currentDrive <- changeDriveIfNeeded(currentDrive, sourcedrive, FALSE);
        bdio_fclose(fHandleIn);
    }
    else
    {
        bdio_printexecres(fHandleIn);
    }
}

byte main()
{
    word Pargs;
    word result;
    word PtgtArgs;
    byte sourcedrv;
    byte targetdrv;
    byte len;

    upstring(BDIO_CMDPROMPTADDR);
    Pargs <- strnextword(BDIO_CMDPROMPTADDR);

    //help only for a word that is exactly -H (end of line right after it)
    if((getswitch(Pargs, "H") = 1) && (peek8(Pargs + 2) = NULLCHAR))
    {
        printusage("copy file",
            "[d:]srcfname.ext",
            "[d:]dstfname.ext");
    }
    else
    {
        //take the target before argfile terminates the source word;
        //terminating before it keeps the old result for a missing target
        PtgtArgs <- strnextword(Pargs);
        poke8(PtgtArgs - 1, NULLCHAR);

        result <- argfile(Pargs, INFILEBDIONAME_ADDR);
        sourcedrv <- result;

        result <- argfile(PtgtArgs, OUTFILEBDIONAME_ADDR);
        targetdrv <- result;

        copy(sourcedrv, INFILEBDIONAME_ADDR, targetdrv, OUTFILEBDIONAME_ADDR);
    }

    putnl();
}