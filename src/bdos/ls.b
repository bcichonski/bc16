#code 0x5000
#heap 0x7000

#include stdio.b
#include bdosh.b

byte main()
{
    word res;
    res <- bdio_call(BDIO_FBINOPENR, "", 0x0000);

    printf("bdos call res: 0x%w%n", res);
}