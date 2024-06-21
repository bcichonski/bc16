#code 0x0f00
#heap 0x2f00

#include stdio.b
#include bdio.b

byte showerror(byte code)
{
    puts("error: 0x");
    putb(code);
    putnl();
}

byte printdrive(byte drive)
{
    if(drive = BDIO_DRIVEA)
    {
        puts("A>");
    }
    else
    {
        puts("B>");
    }
}

byte printexecres(byte execres)
{
    puts("error: ");
    if(execres = BDIO_FOPEN_FDD_NOT_READY)
    {
        puts("fdd not ready");
    }
    if(execres = BDIO_FOPEN_ATTR_NOREAD)
    {
        puts("reading not allowed");
    }
    if(execres = BDIO_FOPEN_FNAME_NOTFOUND)
    {
        puts("file not found");
    }
    if(execres = BDIO_FEXEC_ATTR_NOEXEC)
    {
        puts("execution not allowed");
    }
    if(execres = BDIO_FEXEC_FDESCFCAT_ERR)
    {
        puts("catalogue and file handle mismatch");
    }
    if(execres = BDIO_FEXEC_OUTOFMEM)
    {
        puts("not enough user memory");
    }
    if(execres = BDIO_FEXEC_SECTFAIL)
    {
        puts("not all sectors loaded");
    }
    puts(" 0x");
    putb(execres);
    putnl();
}

byte printhelp()
{
    putsnl("exit - stops entire system");
    putsnl("eject - goes back to BCOS");
    putsnl("help - prints this");
    putsnl("anything else - execute program from disk");
}

byte main()
{
    byte res;
    byte loop;
    byte drive;
    byte hardkill;

    bdio_tracksector_get(0,0);

    putsnl("bDOS 1.0 shell");
    putw(bdio_freemem());
    putsnl(" bytes free");

    res <- bdio_setdrive(BDIO_DRIVEA);
    putsnl("A");

    if(res != FDD_RESULT_OK)
    {
        putsnl("B");
        showerror(res);
    }

    putsnl("C");

    loop <- TRUE;
    hardkill <- TRUE;

    while(loop)
    {
        putsnl("D");
        
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
                hardkill <- FALSE;
                handled <- TRUE;
            }

            if(!handled)
            {
                res <- bdio_execute(BDIO_CMDPROMPTADDR);
                
                if(res != BDIO_FEXEC_OK)
                {
                    printexecres(res);
                }
            }
        }
    }

    puts("bye!");

    if(hardkill)
    {
        asm "kil";
    }
}