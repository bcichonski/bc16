#include std.b
#include stdio.b
#include stdmem.b
#include strings.b

#define MAXLINELENGTH 128
#define TEVARS_SIZE 6
#define TEVARS_TOTALLINES 0
#define TEVARS_PFIRSTLINE 2
#define TEVARS_ARG1 4
#define TEVARS_ARG2 6
#define TELINE_PNEXT 0
#define TELINE_NUMBER 2
#define TELINE_TEXT 4
#define TELINE_HEADSIZE 5

byte printHelp() 
{
    putsnl("i <n> <s> - insert new lines starting from line number <n> with step <s>");
    putsnl("h - help");
    putsnl("q - quit");
}

byte parse2args(word PinputBuf, word PtextedVars)
{
    word arg1;
    word arg2;
    word Pwstart;
    word Pwend;
    byte error;
    error <- 0;

    Pwstart <- strnextword(PinputBuf+1);
    Pwend <- strnextword(Pwstart);

    if(Pwstart) {
        if(Pwend) {
            poke8(Pwend - 1, 0);
            arg1 <- parsedecw(Pwstart, 5);
            arg2 <- parsedecw(Pwend, 5);

            poke16(PtextedVars + TEVARS_ARG1, arg1);
            poke16(PtextedVars + TEVARS_ARG2, arg2);
        }
        else {
            putsnl("Error. Expected argument <s>.");
            error <- 1;
        }
    }
    else
    {
        putsnl("Error. Expected argument <n>.");
        error <- 1;
    }

    return error;
}

word findPreviousLine(word PtextedVars, word lineNumber)
{
    word PcurrLine;
    word PprevLine;
    word prevLineNumber;

    PcurrLine <- #(PtextedVars + TEVARS_PFIRSTLINE);
    PprevLine <- PcurrLine;
    prevLineNumber <- #(PprevLine + TELINE_NUMBER);
    
    while(PcurrLine && lineNumber < prevLineNumber) 
    {
        PprevLine <- PcurrLine;
        prevLineNumber <- #(PprevLine + TELINE_NUMBER);

        PcurrLine = #(PcurrLine + TELINE_PNEXT);
    }

    return PprevLine;
}

byte incTotalLines(word PinputBuf, word increment)
{
    word totalLines;

    totalLines <- #(PinputBuf + TEVARS_TOTALLINES);
    totalLines <- totalLines + increment;

    poke16(PinputBuf + TEVARS_TOTALLINES, totalLines);
}

byte insertLine(word PinputBuf, word PtextedVars, word lineNumber) 
{
    byte continue;
    continue <- 1;

    putdecw(lineNumber);
    puts(": ");
    readsn(PinputBuf, MAXLINELENGTH);

    if(#PinputBuf)
    {
        word lineLength;
        word PnewLine;
        word PprevLine;
        word PnextLine;
        word PfirstLine;

        lineLength <- strnlen8(PinputBuf, MAXLINELENGTH);
        PnewLine <- malloc(lineLength + TELINE_HEADSIZE);
        PfirstLine <- #(PtextedVars + TEVARS_PFIRSTLINE);

        strcpy(PinputBuf, PnewLine + TELINE_HEADSIZE);

        PprevLine <- findPreviousLine(PtextedVars, lineNumber);
        poke16(PnewLine + TELINE_NUMBER, lineNumber);

        if(PprevLine) 
        {
            if(PprevLine = PfirstLine) 
            {
                PnextLine = #(PprevLine + TELINE_PNEXT);

                poke16(PprevLine + TELINE_PNEXT, PnewLine);
                poke16(PnewLine + TELINE_PNEXT, PnextLine);
            }
            else 
            {
                PnextLine = PfirstLine;

                poke16(PnewLine + TELINE_PNEXT, PnextLine);
                poke16(PtextedVars + TEVARS_PFIRSTLINE, PnewLine);
            }
        }
        else
        {
            poke16(PnewLine + TELINE_PNEXT, NULL);

            poke16(PtextedVars + TEVARS_PFIRSTLINE, PnewLine);
        }

        incTotalLines(PinputBuf, 1);
    }
    else
    {
        continue <- 0;
    }

    return continue;
}


byte insertLines(word PinputBuf, word PtextedVars)
{
    word lineNumber;
    word lineNumberStep;
    byte error;

    error <- parse2args(PinputBuf, PtextedVars);

    if(!error)
    {
        lineNumber <- #(PtextedVars + TEVARS_ARG1);
        lineNumberStep <- #(PtextedVars + TEVARS_ARG2);

        byte continue;
        continue <- 1;

        while(continue) 
        {
            continue <- insertLine(PinputBuf, PtextedVars, lineNumber);
            lineNumber <- lineNumber + lineNumberStep;
        }
    }
}

byte mainLoop(word PinputBuf, word PtextedVars) 
{
    byte choice;
    byte continue;
    byte knownCommand;
    word firstLine;

    continue <- 1;
    firstLine <- NULL;
    
    while(continue) {
        puts("texted>");
        readsn(PinputBuf, MAXLINELENGTH - 1);

        choice <- peek8(PinputBuf);
        knownCommand <- 0;

        if(choice = 'i') {
            insertLines(PinputBuf, PtextedVars);
            knownCommand <- 1;
        }

        if(choice = 'h')
        {
            printHelp();
            knownCommand <- 1;
        }

        if(choice = 'q')
        {
            continue <- 0;
            knownCommand <- 1;
        }

        if(!knownCommand) {
            putsnl("Unknown command.");
        }
    }
}

byte initVariables(word PtextedVars) {
    poke16(PtextedVars + TEVARS_SIZE, 0);
    poke16(PtextedVars + TEVARS_PFIRSTLINE, NULL);
}

byte main()
{
    word PinputBuf;
    word PtextedVars;
    putsnl("TextEd v1.0");
    putsnl("type h for help");

    PtextedVars <- malloc(TEVARS_SIZE);
    initVariables(PtextedVars);
    PinputBuf <- malloc(MAXLINELENGTH);
    mainLoop(PinputBuf, PtextedVars);

    mfree(PinputBuf);
    mfree(PtextedVars);
    putsnl("Bye!");
}