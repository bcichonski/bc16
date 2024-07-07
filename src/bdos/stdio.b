#define PRINTF_FORMATCHAR 0x25
#define PRINTF_NEWLINECHAR 'n'
#define PRINTF_HEX8 'x'
#define PRINTF_HEX16 'w'
#define PRINTF_STRING 's'

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

byte printf(word PformatStr)***
{
    PformatStr;
    asm "cal :inc16";
    asm "mov cs, ds";
    asm "mov ci, di";
    asm ".mv dsdi, :sys_stdprntf";
    asm "cal :poke16";
    
    while(PformatStr)
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

        asm "stdprntf_frmt: pop a";
        PformatStr <- PformatStr + 1;
        asm "mov a, #csci";
        asm "psh a";

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
        PRINTF_NEWLINECHAR;
        asm "pop a";
        asm "psh a";
        asm "sub ci";
        asm "jmr nz, :stdprntf_nnwl";
        asm "cal :print_newline";
        asm ".mv csci, :stdprntf_nxtf";
        asm "xor a";
        asm "jmp z, csci";

        asm "stdprntf_nnwl: nop";
        PRINTF_HEX8;
        asm "pop a";
        asm "psh a";
        asm "sub ci";
        asm "jmr nz, :stdprntf_nh8";
        
        asm ".mv dsdi, :sys_stdprntf";
        asm "cal :peek16";
        asm "mov ds, cs";
        asm "mov di, ci";
        asm "cal :peek16";
        asm "pop a";
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
        PRINTF_HEX16;
        asm "pop a";
        asm "psh a";
        asm "sub ci";
        asm "jmr nz, :stdprntf_nh16";
       
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
        PRINTF_STRING;
        asm "pop a";
        asm "psh a";
        asm "sub ci";
        asm "jmr nz, :stdprntf_nxtf";
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
