#code 0x6000
#heap 0xa000

#include std.b
#include bdosh.b

word get_stackhead()
{
    asm ".mv dsdi, :sys_stackhead";
    asm "cal :peek16";
}

word find(word limit, word target)
{
    word i;
    word j;
    i <- 0;
    while(i < limit)
    {
        j <- 0;
        while(j < limit)
        {
            if(i * 10 + j = target)
            {
                if(j > 0)
                {
                    return i * 100 + j;
                }
                return 7777;
            }
            j <- j + 1;
        }
        i <- i + 1;
    }
    return 9999;
}

word fact(word n)
{
    word r;
    if(n < 2)
    {
        return 1;
    }
    r <- fact(n - 1);
    return n * r;
}

word fib(word n)
{
    word a;
    word b;
    if(n < 2)
    {
        return n;
    }
    a <- fib(n - 1);
    b <- fib(n - 2);
    return a + b;
}

word classify(word a, word b, word c)
{
    word t;
    t <- 0x0100;
    if(a > 5)
    {
        if(b > 5)
        {
            if(c > 5)
            {
                return t + 1;
            }
            else
            {
                return t + 2;
            }
        }
        else
        {
            if(c = 0)
            {
                return t + 3;
            }
        }
        return t + 4;
    }
    else
    {
        if(b = a)
        {
            return t + 5;
        }
        else
        {
            if(c = 9)
            {
                return t + 6;
            }
            t <- t + 7;
        }
    }
    return t;
}

byte pick(byte x)
{
    if(x = 1)
    {
        return 0x41;
    }
    else
    {
        if(x = 2)
        {
            return 0x42;
        }
        else
        {
            return 0x43;
        }
    }
}

word deep(word n)
{
    word k;
    k <- n;
    if(n > 0)
    {
        if(n > 1)
        {
            if(n > 2)
            {
                return deep(n - 1) + k;
            }
            return deep(n - 1) + 100;
        }
        return 1000;
    }
    return 0;
}

byte main()
{
    word x;
    word y;
    word z;
    word before;
    word after;
    x <- 0x1111;
    z <- 0x3333;
    before <- get_stackhead();
    y <- find(5, 23);
    putwnl(x);
    putwnl(y);
    putwnl(z);
    putwnl(find(5, 30));
    putwnl(find(3, 99));
    putwnl(fact(6));
    putwnl(fib(10));
    putwnl(classify(9, 9, 9));
    putwnl(classify(9, 9, 1));
    putwnl(classify(9, 1, 0));
    putwnl(classify(9, 1, 1));
    putwnl(classify(2, 2, 0));
    putwnl(classify(2, 3, 9));
    putwnl(classify(2, 3, 1));
    putwnl(pick(1));
    putwnl(pick(2));
    putwnl(pick(7));
    putwnl(deep(5));
    after <- get_stackhead();
    putwnl(x);
    putwnl(z);
    putwnl(before);
    putwnl(after);
    putsnl("done");
    return 0;
}
