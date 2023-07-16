#include stdio.b

byte foo()
{
    return 1;
}

byte main()
{
    byte res;
    res <- foo();
    putb(res);
}
