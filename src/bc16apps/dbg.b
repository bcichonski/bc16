#include stdio.b

byte baz() 
{
    return 2;
}

byte foo()
{
    return baz();
}

byte main()
{
    byte res;
    res <- foo();
    putb(res);
}
