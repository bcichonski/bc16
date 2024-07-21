#code 0x5000
#heap 0x7000

#include std.b
#include bdosh.b
#include strings.b

#define CATBUFSECT_ADDR 0x7880
#define FCATATTRIBSTRING_ADDR 0x7850
#define FNAMESTRING_ADDR 0x7860
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

byte copy(byte sourcedrive, word Psourcefileext, byte targetdrive, word Ptargetfileext)
{

}


byte main()
{
    word Pargs;
    word result;
    word PsrcFileNameExt;
    word PtgtFileNameExt;
    byte sourcedrv;
    byte targetdrv;

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

        printf("Copying %x:%s to %x:%s.%n", sourcedrv, PsrcFileNameExt, targetdrv, PtgtFileNameExt);
    }
}