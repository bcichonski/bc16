byte funrec(byte param)
{
    if(param) {
        return param + funrec(param - 1);
    }

    return 0;
}

byte main()
{
    return funrec(10);
}