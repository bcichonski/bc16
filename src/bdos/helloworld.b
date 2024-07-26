#code 0x5000
#heap 0x7000

//#include std.b
//#include bdosh.b
//#include strings.b
#include stdio.b

byte main()
{
    putsnl("Hello world!");

    //word a;

    //mfill(0x7700, 0xff, 0xab);

    //putsnl("fill");
    
    //memcpy(0x7700, 0x7900, 0xff);

    //putsnl("memcopy");

    putwnl(0x8000 >> 0);
    putwnl(0x8000 >> 1);
    putwnl(0x8000 >> 2);
    putwnl(0x8000 >> 3);
    putwnl(0x8000 >> 4);
    putwnl(0x8000 >> 5);
    putwnl(0x8000 >> 6);
    putwnl(0x8000 >> 7);
    putwnl(0x8000 >> 8);
    putwnl(0x8000 >> 9);
    putwnl(0x8000 >> 10);
    putwnl(0x8000 >> 11);
    putwnl(0x8000 >> 12);
    putwnl(0x8000 >> 13);
    putwnl(0x8000 >> 14);
    putwnl(0x8000 >> 15);
    putwnl(0x8000 >> 16);
}