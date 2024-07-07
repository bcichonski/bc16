#code 0x0f00
#heap 0x3f00

#include std.b
#include stdio.b
#include strings.b
#include bdio.b

byte printdrive(byte drive)
{
    word driveLetter;
    driveLetter <- "?";
    if(drive = BDIO_DRIVEA)
    {
        driveLetter <- "A";
    }
    else
    {
        if(drive = BDIO_DRIVEB) 
        {
            driveLetter <- "B";
        }
    }

    printf("%s>", driveLetter);
}

byte printexecres(byte execres)
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
        errorMessage <- "catalogue and file handle mismatch";
    }
    if(execres = BDIO_FEXEC_OUTOFMEM)
    {
        errorMessage <- "not enough user memory";
    }
    if(execres = BDIO_FEXEC_SECTFAIL)
    {
        errorMessage <- "not all sectors loaded";
    }

    printf("error: %s (0x%x)%n", errorMessage, execres);
}

byte printhelp()
{
    putsnl("exit - stops entire system");
    putsnl("eject - goes back to BCOS");
    putsnl("help - prints this");
    putsnl("anything else - execute program from disk");
}

byte eject()
{
    asm "mov a, 0x2d";
    asm "psh a";
    asm "pop f";
    asm "cal :os_metacall";
}

byte execute(word Pfnameext)
{
    byte result;
    byte len;
    word dotpos;

    upstring(Pfnameext);
    len <- strnlen8(Pfnameext);

    while(len < 8)
    {
        poke8(Pfnameext + len, 0x20);
        len <- len + 1;
    }
    strcpy("PRG", Pfnameext + len);

    result <- bdio_execute(Pfnameext);

    return result;
}

byte main()
{
    byte res;
    byte loop;
    byte drive;
    byte hardkill;

    printf("bDOS 1.0 shell%n%w bytes free%nreading disc...", bdio_freemem());

    res <- bdio_setdrive(BDIO_DRIVEA);

    if(res != FDD_RESULT_OK)
    {
        printf("error: 0x%x%n", res);
    }

    loop <- TRUE;
    hardkill <- TRUE;
    putnl();

    while(loop)
    {
        byte promptlen;

        drive <- bdio_getdrive();
        printdrive(drive);
        
        promptlen <- readsn(BDIO_CMDPROMPTADDR, BDIO_CMDPROMPTLEN);
        if(promptlen)
        {
            byte handled;
            handled <- FALSE;

            res <- strncmp(BDIO_CMDPROMPTADDR, "exit", 4);
            if(res = STRCMP_EQ)
            {
                loop <- FALSE;
                handled <- TRUE;
                hardkill <- TRUE;
            }
            
            res <- strncmp(BDIO_CMDPROMPTADDR, "help", 4);
            if(res = STRCMP_EQ)
            {
                printhelp();
                handled <- TRUE;
            }

            res <- strncmp(BDIO_CMDPROMPTADDR, "eject", 5);
            if(res = STRCMP_EQ)
            {
                loop <- FALSE;
                hardkill <- FALSE;
                handled <- TRUE;
            }

            if(!handled)
            {
                res <- execute(BDIO_CMDPROMPTADDR);
                
                if(res != BDIO_FEXEC_OK)
                {
                    printexecres(res);
                }
            }
        }
    }

    putsnl("bye!");

    if(hardkill)
    {
        asm "kil";
    }
    
    eject();
}