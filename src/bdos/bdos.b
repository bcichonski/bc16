#code 0x0f00
#heap 0x3f00

#include std.b
#include stdio.b
#include strings.b
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

    printf("test %w %x %s %n", 0xabcd, 0x12, "aaaaaaaa");

    putsnl("bDOS 1.0 shell");
    putw(bdio_freemem());
    putsnl(" bytes free");
    puts("scanning disc...");

    res <- bdio_setdrive(BDIO_DRIVEA);

    if(res != FDD_RESULT_OK)
    {
        showerror(res);
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