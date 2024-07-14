#code 0x5000
#heap 0x7000

#include std.b
#include bdosh.b
#include strings.b

byte main()
{
    putsnl("Hello world!");

    word a;

    mfill(0x7700, 0xff, 0xab);

    putsnl("fill");
    
    memcpy(0x7700, 0x7900, 0xff);

    putsnl("memcopy");
}