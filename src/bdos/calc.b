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
}

byte calc(byte operator)
{
    word Pinputstr;
    Pinputstr <- INPUTBUFFER;

    puts("1>");
    readsn(Pinputstr, 6);
    word arg1;
    arg1 <- parsedecw(Pinputstr, 6);

    puts("2>");
    readsn(Pinputstr, 6);
    word arg2;
    arg2 <- parsedecw(Pinputstr, 6);

    if(operator = '+') {
        arg1 <- arg1 + arg2;
    }
    
    if(operator = '-') {
        arg1 <- arg1 - arg2;
    }

    if(operator = '*') {
        arg1 <- arg1 * arg2;
    }

    if(operator = '/') {
        arg1 <- arg1 / arg2;
    }

    puts("res>");
    putdecw(arg1);
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
    byte handled;
    handled <- 0;

    if(command = 'h')
    {
        print_help();
        handled <- 1;
    }

    if(command = 'q')
    {
        result <- 0;
        handled <- 1;
    }

    if(!handled) {
        calc(command);
    }

    return result;
}

byte main()
{
    puts("calc v1.0");
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
