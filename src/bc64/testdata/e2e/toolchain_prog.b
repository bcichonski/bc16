#code 0x6000
#heap 0xf000

#include std.b
#include stdio.b

word square(word x)
{
    return x * x;
}

byte main()
{
    word i;
    word sum;

    sum <- 0;
    i <- 1;
    while(i < 6)
    {
        sum <- sum + square(i);
        i <- i + 1;
    }

    putsnl("toolchain ok");
    putdecwnl(sum);
    putwnl(sum + 0x1000);
}
