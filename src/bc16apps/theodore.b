#include std.b
#include stdio.b
#include stdmem.b

#define PINPUTBUFLEN 32
#define MAXSTOPS 100

word getRandomSeed(word PinputBuf, word maxValue)
{
    word rand;
    word temp;

    puts("What time is it? (hhmm) ");
    readsn(PinputBuf, PINPUTBUFLEN);

    rand <- parsedecw(PinputBuf, PINPUTBUFLEN);
    rand <- rand * 5 + 1;
    temp <- rand / 9887;
    rand <- rand - temp * 9887;
    rand <- rand * 3 + 1;
    temp <- rand / maxValue;
    rand <- rand - temp * maxValue;

    return rand;
}

byte mainLoop(word PinputBuf, byte theodoreStopNumber)
{
    byte theodoreFound;
    byte playerStop;
    byte playerExit;

    theodoreFound <- 0;
    playerStop <- 0;
    playerExit <- 0;

    while(!(theodoreFound + playerExit)) 
    {
        puts("Where is uncle Theodore?");
        putnl();
        puts("Type train stop number (0..");
        putdecw(MAXSTOPS);
        puts("): ");

        readsn(PinputBuf, PINPUTBUFLEN);
        playerStop <- parsedecw(PinputBuf, PINPUTBUFLEN);

        if(playerStop < MAXSTOPS) 
        {
            if(playerStop = theodoreStopNumber) 
            {
                puts("Yes! You have found uncle Theodore!");
                putnl();
                theodoreFound <- 1;
            }

            if(theodoreStopNumber < playerStop) 
            {
                puts("Uncle Theodore went south.");
                putnl();
            }

            if(playerStop < theodoreStopNumber) 
            {
                puts("Uncle Theodore went north.");
                putnl();
            }
        }

        if (playerStop >= MAXSTOPS) 
        {
            playerExit <- 1;
        }
    }
}

byte main() 
{
    word PinputBuf;
    word rand;
    
    puts("Looking for ucle Theodore v1.0");
    putnl();

    PinputBuf <- malloc(PINPUTBUFLEN);

    rand <- getRandomSeed(PinputBuf, MAXSTOPS);

    mainLoop(PinputBuf, rand);
    mfree(PinputBuf);
    
    puts("Bye!");
    putnl();

    return 0;
}