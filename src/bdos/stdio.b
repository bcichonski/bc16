#define PRINTF_FORMATCHAR 0x25
#define PRINTF_STATE_NORMAL 0x01
#define PRINTF_STATE_FORMAT 0x02
#define PRINTF_STATE_END 0x00

byte putdigit(byte digit)
{
    digit;
    asm "mov a, ci";
    asm "cal :printhex4";
} 

byte putb(byte value)
{
    value;
    asm "mov a, ci";
    asm "cal :printhex8";
}

byte putw(word value)
{
    value;
    asm "cal :printhex16";
}

byte putwnl(word value)
{
    value;
    asm "cal :printhex16";
    asm "cal :print_newline";
}

byte putnl()
{
    asm "cal :print_newline";
}

byte puts(word Pstr)
{
    //result of this expression is value of Pstr in csci registers
    Pstr;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "cal :printstr";
}

byte putsnl(word Pstr)
{
    //result of this expression is value of Pstr in csci registers
    Pstr;
    asm "mov ds, cs";
    asm "mov di, ci";
    asm "cal :printstr";
    asm "cal :print_newline";
}

byte readsn(word Pbuf, byte maxlen)
{
    Pbuf;
    asm "psh cs";
    asm "psh ci";
    maxlen;
    asm "pop di";
    asm "pop ds";
    asm "cal :readstr";
}

byte putdecw(word value)
{
    byte digit;
    word divisor;
    byte nonzero;

    divisor <- 10000;
    nonzero <- 0;

    while(divisor) 
    {
        digit <- value / divisor;
        value <- value - digit * divisor;

        if(digit & (divisor = 1)) 
        {
            nonzero <- 1;
        }

        if(nonzero) {
            putdigit(digit);
        }
        
        divisor <- divisor / 10;
    }
}

byte putdecwnl(word value)
{
    putdecw(value);
    asm "cal :print_newline";
}

byte iopeek8(word Paddr)
{
    Paddr;
    asm "mov a, #csci";
    asm "mov cs, 0x00";
    asm "mov ci, a";
}

byte iopoke8(word Paddr, byte value) 
{
    value;
    asm "mov a, ci";
    asm "psh a";
    Paddr;
    asm "pop a";
    asm "mov #csci, a";
}

byte iopoke16(word Paddr, word value) 
{
    Paddr;
    asm "psh cs";
    asm "psh ci";
    value;
    asm "pop di";
    asm "pop ds";
    asm "cal :poke16";
}

byte printf(word PformatStr)***
{
    PformatStr;
    asm "cal :inc16";
    asm "mov cs, ds";
    asm "mov ci, di";
    asm ".mv dsdi, :sys_stdprntf";
    asm "cal :poke16";
    
    while((printfPLEN > 0) && PformatStr)
    {
        PformatStr;
        asm "mov a, #csci";
        asm "psh a";
        asm ".mv csci, :stdprntf_end";
        asm "jmp z, csci";

        asm "mov ci, PRINTF_FORMATCHAR";
        asm "sub ci";
        asm "jmr z, :stdprntf_frmt";
        asm "pop a";
        asm "mov cs, 0x01";
        asm "out #cs, a";
        asm ".mv csci, :stdprntf_next";
        asm "xor a";
        asm "jmp z, csci";

        asm "stdprntf_frmt: nop";
        PformatStr <- PformatStr + 1;
        asm "pop a";
        asm "mov a, #csci";
        asm "psh a";
        asm "mov ci, PRINTF_FORMATCHAR";

        asm "mov ci, PRINTF_FORMATCHAR";
        asm "sub ci";
        asm "jmr nz, :stdprntf_nprc";
        asm "pop a";
        asm "mov cs, 0x01";
        asm "out #cs, a";
        asm ".mv csci, :stdprntf_next";
        asm "xor a";
        asm "jmp z, csci";

        asm "stdprntf_nprc: nop";
        'n';
        asm "pop a";
        asm "psh a";
        asm "sub ci";
        asm "jmr nz, :stdprntf_nnwl";
        asm "pop a";
        asm "cal :print_newline";
        asm ".mv csci, :stdprntf_nxtf";
        asm "xor a";
        asm "jmp z, csci";

        asm "stdprntf_nnwl: nop";
        'x';
        asm "pop a";
        asm "psh a";
        asm "sub ci";
        asm "jmr nz, :stdprntf_nh8";
        asm "pop a";
        
        asm ".mv dsdi, :sys_stdprntf";
        asm "cal :peek16";
        asm "mov ds, cs";
        asm "mov di, ci";
        asm "cal :peek16";
        asm "psh ci";
        
        asm "cal :inc16";
        asm "mov cs, ds";
        asm "mov ci, di";
        asm ".mv dsdi, :sys_stdprntf";
        asm "cal :poke16";

        asm "pop a";
        asm "cal :printhex8";
        asm ".mv csci, :stdprntf_nxtf";
        asm "xor a";
        asm "jmp z, csci";

        asm "stdprntf_nh8: nop";
        'w';
        asm "pop a";
        asm "psh a";
        asm "sub ci";
        asm "jmr nz, :stdprntf_nh16";
        asm "pop a";
       
        asm ".mv dsdi, :sys_stdprntf";
        asm "cal :peek16";
        asm "mov ds, cs";
        asm "mov di, ci";
        asm "cal :peek16";
        asm "psh ci";
        asm "psh cs";
        
        asm "cal :inc16";
        asm "mov cs, ds";
        asm "mov ci, di";
        asm ".mv dsdi, :sys_stdprntf";
        asm "cal :poke16";

        asm "pop cs";
        asm "pop ci";
        asm "cal :printhex16";
        asm ".mv csci, :stdprntf_nxtf";
        asm "xor a";
        asm "jmp z, csci";

        asm "stdprntf_nh16: nop";
        's';
        asm "pop a";
        asm "psh a";
        asm "sub ci";
        asm "jmr nz, :stdprntf_nxtf";
        asm "pop a";
        asm ".mv dsdi, :sys_stdprntf";
        asm "cal :peek16";
        asm "mov ds, cs";
        asm "mov di, ci";
        asm "cal :peek16";
        asm "psh ci";
        asm "psh cs";

        asm "cal :inc16";
        asm "mov cs, ds";
        asm "mov ci, di";
        asm ".mv dsdi, :sys_stdprntf";
        asm "cal :poke16";

        asm "pop ds";
        asm "pop di";
        asm "cal :printstr";

        asm "stdprntf_nxtf: pop a";
        printfPLEN <- printfPLEN - 1;
        asm "xor a";
        asm "jmr z, :stdprntf_next";

        asm "stdprntf_end: pop a";
        PformatStr <- 0;
        asm "xor a";
        asm "jmr z, :stdprntf_cont";

        asm "stdprntf_next: nop";
        PformatStr <- PformatStr + 1;

        asm "stdprntf_cont: nop";
    }

    return 0;
}
