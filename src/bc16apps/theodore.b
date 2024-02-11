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
        putsnl("Where is uncle Theodore?");
        puts("Type train stop number (0..");
        putdecw(MAXSTOPS);
        puts("): ");

        readsn(PinputBuf, PINPUTBUFLEN);
        playerStop <- parsedecw(PinputBuf, PINPUTBUFLEN);

        if(playerStop < MAXSTOPS) 
        {
            if(playerStop = theodoreStopNumber) 
            {
                putsnl("Yes! You have found uncle Theodore!");
                theodoreFound <- 1;
            }

            if(theodoreStopNumber < playerStop) 
            {
                putsnl("Uncle Theodore went south.");
            }

            if(playerStop < theodoreStopNumber) 
            {
                putsnl("Uncle Theodore went north.");
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
    
    putsnl("Looking for ucle Theodore v1.0");

    PinputBuf <- malloc(PINPUTBUFLEN);

    rand <- getRandomSeed(PinputBuf, MAXSTOPS);

    mainLoop(PinputBuf, rand);
    mfree(PinputBuf);
    
    putsnl("Bye!");

    return 0;
}