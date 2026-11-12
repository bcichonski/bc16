#code 0x6000
#heap 0xf000

#include std.b
//#include bdosh.b
//#include strings.b
#include stdio.b

byte main()
{
    putsnl("Hello world!");

    word a;
    a <- 10;

    putdecwnl(a);
}