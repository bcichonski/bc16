#code 0x0C00

#include std.b
#include stdio.b
#include stdmem.b
#include strings.b

#define MAXLINELENGTH 64
#define MAXLINENUMBER 0xffff
#define TEVARS_SIZE 8
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
    putsnl("p <n> <m> - print lines from <n> to <m>");
    putsnl("d <n> <m> - delete lines from <n> to <m>");
    putsnl("m - memory stats");
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
    word currLineNumber;

    PcurrLine <- #(PtextedVars + TEVARS_PFIRSTLINE);
    PprevLine <- PcurrLine;
   
    currLineNumber <- #(PcurrLine + TELINE_NUMBER);
    prevLineNumber <- currLineNumber;
    
    while(PcurrLine && currLineNumber < lineNumber) 
    {
        PprevLine <- PcurrLine;
        prevLineNumber <- currLineNumber;

        PcurrLine <- #(PcurrLine + TELINE_PNEXT);
        currLineNumber <- #(PcurrLine + TELINE_NUMBER);
    }

    if(currLineNumber >= lineNumber)
    {
        PcurrLine <- PprevLine;
    }
    return PcurrLine;
}

word findMaxLineEndAddress(word PtextedVars)
{
    word PcurrLine;
    word PmaxLineAddress;

    PmaxLineAddress <- 0;

    PcurrLine <- #(PtextedVars + TEVARS_PFIRSTLINE);
    
    while(PcurrLine) 
    {
        if (PmaxLineAddress < PcurrLine) 
        {
            PmaxLineAddress <- PcurrLine;
        }

        PcurrLine <- #(PcurrLine + TELINE_PNEXT);
    }

    byte length;
    PcurrLine <- #(PmaxLineAddress + TELINE_TEXT);
    length <- strnlen8(PcurrLine, MAXLINELENGTH);

    return PmaxLineAddress + TELINE_HEADSIZE + length;
}

byte setTotalLines(word PtextedVars, word change, byte inc)
{
    word totalLines;

    totalLines <- #(PtextedVars + TEVARS_TOTALLINES);
    if (inc) 
    {
        totalLines <- totalLines + change;
    }
    else
    {
        totalLines <- totalLines - change;
    }

    poke16(PtextedVars + TEVARS_TOTALLINES, totalLines);
}

byte insertLine(word PinputBuf, word PtextedVars, word lineNumber) 
{
    byte continue;
    continue <- 1;
    
    poke16(PinputBuf, 0);
    putdecw(lineNumber);
    puts(": ");
    readsn(PinputBuf, MAXLINELENGTH);

    if(#PinputBuf)
    {
        byte inserted;
        word lineLength;
        word PnewLine;
        word PprevLine;
        word PnextLine;
        word prevLineNumber;
        word nextLineNumber;

        inserted <- 1;
        prevLineNumber <- 0;

        lineLength <- strnlen8(PinputBuf, MAXLINELENGTH);
        PnewLine <- malloc(lineLength + TELINE_HEADSIZE);
        poke16(PnewLine + TELINE_NUMBER, lineNumber);

        strcpy(PinputBuf, PnewLine + TELINE_TEXT);

        PprevLine <- findPreviousLine(PtextedVars, lineNumber);
        if(PprevLine != NULL) 
        {
            prevLineNumber <- #(PprevLine + TELINE_NUMBER);
        }

        if(PprevLine != NULL && (lineNumber > prevLineNumber)) 
        {
            PnextLine <- #(PprevLine + TELINE_PNEXT);
            nextLineNumber <- #(PnextLine + TELINE_NUMBER);

            if (PnextLine = NULL) 
            {
                nextLineNumber <- MAXLINENUMBER;
            }

            if (lineNumber < nextLineNumber) {
                poke16(PnewLine + TELINE_PNEXT, PnextLine);
                poke16(PprevLine + TELINE_PNEXT, PnewLine);
            }
            else 
            {
                if (lineNumber = nextLineNumber) 
                {
                    word PnextNextLine;
                    PnextNextLine <- #(PnextLine + TELINE_PNEXT);

                    poke16(PprevLine + TELINE_PNEXT, PnewLine);
                    poke16(PnewLine + TELINE_PNEXT, PnextNextLine);
                    mfree(PnextLine);
                    inserted <- 0;
                }
            }
        }
        else
        {
            poke16(PnewLine + TELINE_PNEXT, PprevLine);

            poke16(PtextedVars + TEVARS_PFIRSTLINE, PnewLine);
        }

        if(inserted) 
        {
            setTotalLines(PtextedVars, 1, 1);
        }
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

byte printLines(word PinputBuf, word PtextedVars)
{
    word lineNumberStart;
    word lineNumberEnd;
    byte error;

    error <- parse2args(PinputBuf, PtextedVars);

    if(!error)
    {
        lineNumberStart <- #(PtextedVars + TEVARS_ARG1);
        lineNumberEnd <- #(PtextedVars + TEVARS_ARG2);

        word currentLineNumber;
        word PcurrentLine;
        word PlineText;

        PcurrentLine <- findPreviousLine(PtextedVars, lineNumberStart);
        currentLineNumber <- #(PcurrentLine + TELINE_NUMBER);

        while(PcurrentLine && currentLineNumber <= lineNumberEnd) 
        {
            putdecw(currentLineNumber);
            puts(": ");
            PlineText <- PcurrentLine + TELINE_TEXT;

            putsnl(PlineText);

            PcurrentLine <- #(PcurrentLine + TELINE_PNEXT);
            currentLineNumber <- #(PcurrentLine + TELINE_NUMBER);
        }
    }
}

byte deleteLines(word PinputBuf, word PtextedVars)
{
    word lineNumberStart;
    word lineNumberEnd;
    byte error;

    error <- parse2args(PinputBuf, PtextedVars);

    if(!error)
    {
        lineNumberStart <- #(PtextedVars + TEVARS_ARG1);
        lineNumberEnd <- #(PtextedVars + TEVARS_ARG2);

        word currentLineNumber;
        word PcurrentLine;
        word PstartLine;
        word startLineNumber;
        word PlineText;
        word removedCount;

        PstartLine <- findPreviousLine(PtextedVars, lineNumberStart);
        PcurrentLine <- PstartLine;
        currentLineNumber <- #(PcurrentLine + TELINE_NUMBER);
        startLineNumber <- currentLineNumber;

        if(PcurrentLine && startLineNumber < lineNumberStart) 
        {
            PcurrentLine <- #(PcurrentLine + TELINE_PNEXT);
            currentLineNumber <- #(PcurrentLine + TELINE_NUMBER);
        }
        
        removedCount <- 0;

        while(PcurrentLine && currentLineNumber <= lineNumberEnd) 
        {
            mfree(PcurrentLine);
            removedCount <- removedCount + 1;

            PcurrentLine <- #(PcurrentLine + TELINE_PNEXT);
            currentLineNumber <- #(PcurrentLine + TELINE_NUMBER);
        }

        if (PcurrentLine)
        {
            if(removedCount > 0) 
            {
                if(currentLineNumber <= lineNumberEnd) 
                {
                    poke16(PstartLine + TELINE_PNEXT, NULL);
                }
                else 
                {
                    if(startLineNumber <= lineNumberStart) 
                    {
                        poke16(PstartLine + TELINE_PNEXT, PcurrentLine);
                    }
                    else
                    {
                        poke16(PtextedVars + TEVARS_PFIRSTLINE, PcurrentLine);
                    }
                }
            }
        }
        else
        {
            if(removedCount > 0) 
            {
                if(startLineNumber <= lineNumberStart) 
                {
                    poke16(PstartLine + TELINE_PNEXT, NULL);
                }
                else 
                {
                    poke16(PtextedVars + TEVARS_PFIRSTLINE, NULL);
                }
            }
        }
        
        setTotalLines(PtextedVars, removedCount, 0);
        putdecw(removedCount);
        putsnl(" lines removed");
    }
}

byte memStat(word PinputBuf, word PtextedVars)
{
    word memtotal;
    word firstLineNumber;
    word PfirstLine;
    word PlastLineLastByte;
    word totalLines;

    memtotal <- mtotal();
    totalLines <- #(PtextedVars + TEVARS_TOTALLINES);

    PfirstLine <- #(PtextedVars + TEVARS_PFIRSTLINE);
    firstLineNumber <- #(PfirstLine + TELINE_NUMBER);

    PlastLineLastByte <- findMaxLineEndAddress(PtextedVars);

    puts("total lines: "); putdecwnl(totalLines);
    puts("from: ");putdecw(firstLineNumber);puts(" (");putw(PfirstLine);putsnl(")");
    puts("last byte: ");putwnl(PlastLineLastByte);
    puts("estimated free memory: ");putdecw(memtotal);putsnl(" bytes");
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

        if(choice = 'p') {
            printLines(PinputBuf, PtextedVars);
            knownCommand <- 1;
        }

        if(choice = 'd') {
            deleteLines(PinputBuf, PtextedVars);
            knownCommand <- 1;
        }

        if(choice = 'm') {
            memStat(PinputBuf, PtextedVars);
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

byte main()
{
    word PinputBuf;
    word PtextedVars;
    putsnl("TextEd v1.1");
    putsnl("type h for help");

    PtextedVars <- malloc(TEVARS_SIZE);
    poke16(PtextedVars + TEVARS_TOTALLINES, 0);
    poke16(PtextedVars + TEVARS_PFIRSTLINE, NULL);
    PinputBuf <- malloc(MAXLINELENGTH);

    mainLoop(PinputBuf, PtextedVars);

    mfree(PinputBuf);
    mfree(PtextedVars);
    putsnl("Bye!");
}