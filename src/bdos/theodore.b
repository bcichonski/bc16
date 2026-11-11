#code 0x6000
#heap 0xf000

#include std.b
#include stdmem.b
#include bdosh.b
#include random.b

#define PINPUTBUFLEN 32
#define MAXSTOPS 100

byte mainLoop(word PinputBuf, word theodoreStopNumber)
{
    byte theodoreFound;
    word playerStop;
    byte playerExit;

    theodoreFound <- 0;
    playerStop <- 0;
    playerExit <- 0;

    while(!(theodoreFound + playerExit)) 
    {
        putsnl("Where is uncle Theodore?");
        puts("Type train stop number (0..99) or 100 to quit: ");

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
    
    putsnl("Looking for uncle Theodore v1.1");

    PinputBuf <- malloc(PINPUTBUFLEN);

    rand <- random(MAXSTOPS);

    mainLoop(PinputBuf, rand);
    mfree(PinputBuf);
    
    putsnl("Bye!");

    return 0;
}