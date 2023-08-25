#include stdio.b
#include stdmem.b

#define INPUTBUFFER 0x0f00

byte print_help() 
{
    puts("+ for addition");
    putnl();
    puts("- for deletion");
    putnl();
    puts("* for multiplication");
    putnl();
    puts("/ for division");
    putnl();
    puts("h for help");
    putnl();
    puts("q for quit");
    putnl();
    return 0;
}

byte runcommand()
{
    word Pinputstr;
    Pinputstr <- INPUTBUFFER;

    puts("calc>");
    readsn(Pinputstr, 32);

    byte command;
    command <- peek8(Pinputstr);

    byte result;
    result <- 1;

    if(command = 'h')
    {
        print_help();
    }

    if(command = 'q')
    {
        result <- 0;
    }

    return result;
}

byte main()
{
    puts("calc v.0.1");
    putnl();
    puts("type h for help");
    putnl();

    byte continue;
    continue <- 1;

    while(continue) 
    {
        continue <- runcommand();
    }

    puts("bye");
    putnl();

    return 0;
}
