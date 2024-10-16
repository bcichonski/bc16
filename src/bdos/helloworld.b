#code 0x5800
#heap 0x7000

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