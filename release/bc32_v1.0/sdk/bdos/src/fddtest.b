#code 0x1000
#heap 0x3000

#include std.b
#include stdio.b
#include strings.b

byte getFddPing()
{
    asm "mov ci, 0x08";
    asm "mov a, 0xf0";
    asm "out #ci, a";
    asm "in a, #ci";
    asm "mov ci, a";
}

byte testFddPing()
{
    putnl();
    byte ret;
    ret <- getFddPing();
    puts("fdd ping: ");
    putb(ret);
    puts(" --> ");
    if(ret = 0x11)
    {
        puts("ok");
    }
    else
    {
        puts("fail");
    }
    putnl();
}



byte main()
{
    puts("fdd test 1.0");
    testFddPing();
    puts("done");
}