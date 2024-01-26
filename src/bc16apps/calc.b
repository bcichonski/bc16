#include std.b
#include stdio.b

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

byte add()
{
    word Pinputstr;
    Pinputstr <- INPUTBUFFER;

    puts("calc.add.1>");
    readsn(Pinputstr, 6);
    word add1;
    add1 <- parsedecw(Pinputstr, 6);

    puts("calc.add.2>");
    readsn(Pinputstr, 6);
    word add2;
    add2 <- parsedecw(Pinputstr, 6);

    add1 <- add1 + add2;

    puts("calc.add>");
    putdecw(add1);
    putnl();
}

byte runcommand()
{
    word Pinputstr;
    Pinputstr <- INPUTBUFFER;

    puts("calc>");
    readsn(Pinputstr, 2);

    byte command;
    command <- peek8(Pinputstr);

    byte result;
    result <- 1;

    if(command = 'h')
    {
        print_help();
    }

    if(command = '+')
    {
        add();
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
