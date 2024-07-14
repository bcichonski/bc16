#code 0x0f00
#heap 0x4f00

#include std.b
#include strings.b
#include bdio.b

#define BCOSMETA_BDOSCALLADDR 0x007e
#define FNAMETEMP_ADDR 0x4f00
#define FNAMETEMP_SIZE 0x0b

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

byte printhelp()
{
    printf("%s%n%s%n%s%n%s%n%s%n",
      "exit - stops entire system",
      "bcos - goes back to BCOS",
      "a:,b: - selects active drive",
      "help - prints this",
      "anything else - execute program from disk");
}

byte eject()
{
    asm "mov a, 0x2d";
    asm "psh a";
    asm "pop f";
    asm "cal :os_metacall";
}

byte changedrive(byte drivechar)
{
    byte currentDrive;
    byte wantedDrive;

    currentDrive <- bdio_getdrive();
    if(drivechar = 'A')
    {
        wantedDrive <- BDIO_DRIVEA;
    }
    else
    {
        wantedDrive <- BDIO_DRIVEB;
    }

    if(currentDrive != wantedDrive)
    {
        bdio_setdrive(wantedDrive);
    }
}

byte execute(word Pfnameext)
{
    byte result;
    byte len;
    word tokenpos;

    len <- strnlen8(Pfnameext);
    result <- BDIO_FEXEC_OK;

    if(len > 0) 
    {
        upstring(Pfnameext);
        
        tokenpos <- strnextword(Pfnameext);

        len <- tokenpos - Pfnameext;

        strncpy(Pfnameext, FNAMETEMP_ADDR, len);

        while(len < 8)
        {
            poke8(FNAMETEMP_ADDR + len, 0x20);
            len <- len + 1;
        }

        strncpy("PRG", FNAMETEMP_ADDR + len, 3);
        poke8(FNAMETEMP_ADDR + FNAMETEMP_SIZE, NULLCHAR);

        result <- bdio_execute(FNAMETEMP_ADDR);
    }

    return result;
}

byte main()
{
    byte res;
    byte loop;
    byte drive;
    byte hardkill;

    asm ".mv csci, :bdio_call";
    asm ".def bdiocalladdr, BCOSMETA_BDOSCALLADDR";
    asm ".mv dsdi, :bdiocalladdr";
    asm "cal :poke16";

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

            res <- strncmp(BDIO_CMDPROMPTADDR, "bcos", 5);
            if(res = STRCMP_EQ)
            {
                loop <- FALSE;
                hardkill <- FALSE;
                handled <- TRUE;
            }

            res <- peek8(BDIO_CMDPROMPTADDR + 1) = ':';
            if(res)
            {
                res <- upchar(peek8(BDIO_CMDPROMPTADDR));
                
                changedrive(res);
                handled <- TRUE;
            }

            if(!handled)
            {
                res <- execute(BDIO_CMDPROMPTADDR);
                
                if(res != BDIO_FEXEC_OK)
                {
                    bdio_printexecres(res);
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