#code 0x6000
#heap 0xa000

#include std.b
#include bdosh.b
#include random.b

byte main()
{
    byte i;

    i <- 0;
    while(i < 8)
    {
        putwnl(random(10));
        i <- i + 1;
    }
    putsnl("full");
    putwnl(random(0));
    putsnl("end");
}
