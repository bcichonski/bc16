#code 0x5000
#heap 0x7000

#include std.b
//#include bdosh.b
//#include strings.b
#include stdio.b

byte main()
{
    putsnl("Hello world!");

    //word a;
    putsnl("fill");
    mfill(0x7700, 0xff, 0xab);
    mfill(0x7900, 0xff, 0xcd);

    putsnl("memcopy");
    memcpy(0x7700, 0x7900, 0x000f);
}