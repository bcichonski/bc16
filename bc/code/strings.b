byte puts(word Pstr)
{
    asm "kil";
    return 0;
}

byte main()
{
    word str;
    str <- "hello world";
    return puts(str);
}