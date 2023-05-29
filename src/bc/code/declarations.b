byte main()
{
    word var1;
    byte var2;
    var1 <- 5;
    var2 <- 4 - 2;
    if(var1)
    {
        var1 <- var2;
    }
    while(var2)
    {
        var2 <- var2 - 1;
    }
    var1 <- "string";
    asm "nop";
    asm "xor a";
}