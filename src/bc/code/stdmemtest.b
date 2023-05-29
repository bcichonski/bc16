#include stdio.b

byte emptyret(byte value)
{
}

byte main()
{
    byte test;
    byte test2;
    puts("test empty and ret 0xab: ");
    test <- emptyret(0xab);
    putb(test);
    test2 <- test = 0xab;
    putb(test2);
    if (test2) 
    {
        puts("ok");
    }
    putnl();
}