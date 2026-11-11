#code 0x6000
#heap 0xa000

#include std.b
#include bdosh.b
#include stdmem.b
#include strings.b
#include bdostools.b

#define MAXLINELENGTH 80
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
#define MAXFILENAMELEN 12
#define CHAR_LF 0x13

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

    if(peek8(Pwstart)) {
        if(peek8(Pwend)) {
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

    //printf("PcurrLine: %w PprevLine: %w currLineNumber: %w prevLineNumber: %w%n", PcurrLine, PprevLine, currLineNumber, prevLineNumber);
    
    while(PcurrLine && (currLineNumber < lineNumber)) 
    {
        PprevLine <- PcurrLine;
        prevLineNumber <- currLineNumber;

        PcurrLine <- #(PcurrLine + TELINE_PNEXT);
        currLineNumber <- #(PcurrLine + TELINE_NUMBER);

        //printf("PcurrLine: %w PprevLine: %w currLineNumber: %w prevLineNumber: %w%n", PcurrLine, PprevLine, currLineNumber, prevLineNumber);
    }

    if((PcurrLine = NULL) || (currLineNumber >= lineNumber))
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

byte insertLineBuf(word PinputBuf, word PtextedVars, word lineNumber)
{
    byte continue;
    continue <- 1;

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

        if((PprevLine != NULL) && (lineNumber > prevLineNumber)) 
        {
            PnextLine <- #(PprevLine + TELINE_PNEXT);
            nextLineNumber <- #(PnextLine + TELINE_NUMBER);

            if ((PnextLine = NULL) || (lineNumber < nextLineNumber)) {
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

byte insertLine(word PinputBuf, word PtextedVars, word lineNumber) 
{
    poke16(PinputBuf, 0);
    putdecw(lineNumber);
    puts(" ");
    readsn(PinputBuf, MAXLINELENGTH + 1);

    return insertLineBuf(PinputBuf, PtextedVars, lineNumber);   
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

        while(PcurrentLine && (currentLineNumber <= lineNumberEnd)) 
        {
            putdecw(currentLineNumber);
            puts(" ");
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

        if(PcurrentLine && (startLineNumber < lineNumberStart)) 
        {
            PcurrentLine <- #(PcurrentLine + TELINE_PNEXT);
            currentLineNumber <- #(PcurrentLine + TELINE_NUMBER);
        }
        
        removedCount <- 0;

        while(PcurrentLine && (currentLineNumber <= lineNumberEnd)) 
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
    puts("from: ");putdecw(firstLineNumber);
    printf(" (%w) last byte: %w%nestimated free memory: ", PfirstLine, PlastLineLastByte);
    putdecw(memtotal);putsnl(" bytes");
}

byte saveLines(word PtextedVars, byte fHandleOut, word Ptextbuf)
{
    word currentLineNumber;
    word PcurrentLine;
    word PlineText;
    byte result;
    byte lineLen;
    word i;

    PcurrentLine <- #(PtextedVars + TEVARS_PFIRSTLINE);
    currentLineNumber <- #(PcurrentLine + TELINE_NUMBER);
    result <- 1;
    i<-0;

    while(PcurrentLine && result) 
    {
        PlineText <- PcurrentLine + TELINE_TEXT;
        lineLen <- strnlen8(PlineText, MAXLINELENGTH);
        poke8(PlineText + lineLen, CHAR_LF);

        result <- strndecw(currentLineNumber, Ptextbuf, BDIO_FCAT_ENTRY_NAMELEN);
        poke8(Ptextbuf + result, ' ');
        poke8(Ptextbuf + result + 1, NULLCHAR);
        
        result <- bdio_fbinbufwrite(fHandleOut, Ptextbuf, result + 1);
        if(result)
        {
          result <- bdio_fbinbufwrite(fHandleOut, PlineText, lineLen + 1);
        }

        poke8(PlineText + lineLen, NULLCHAR);

        PcurrentLine <- #(PcurrentLine + TELINE_PNEXT);
        currentLineNumber <- #(PcurrentLine + TELINE_NUMBER);
        i <- i + 1;
    }

    if(i && result)
    {
        //make sure that the null char will be at the end of file
        poke8(Ptextbuf, NULLCHAR);
        result <- bdio_fbinbufwrite(fHandleOut, Ptextbuf, 1);
    }
    printf("%w lines saved%n", i);
}

word fileArg(word PinputBuf, word bufLen, word Pverb)
{
    //parses the <file> argument, prints "<verb> <file>..."
    //returns a new buffer of bufLen bytes holding the normalized file name, or NULL on error
    word Pwstart;
    word Pwend;
    word Pbuf;

    Pbuf <- NULL;
    Pwstart <- strnextword(PinputBuf+1);
    Pwend <- strnextword(Pwstart);

    if(peek8(Pwstart))
    {
        if((Pwend - Pwstart) <= MAXFILENAMELEN)
        {
            poke8(Pwend, NULLCHAR);
            Pbuf <- malloc(bufLen);

            bdio_fnormalize(Pwstart, Pbuf);

            printf("%s %s...%n", Pverb, Pwstart);
        }
        else 
        {
            putsnl("Error. <file> too long.");
        }
    }
    else 
    {
        putsnl("Error. Expected argument <file>.");
    }

    return Pbuf;
}

byte saveFile(word PinputBuf, word PtextedVars)
{
    word Ptextbuf;
    byte fHandleOut;
    byte result;

    Ptextbuf <- fileArg(PinputBuf, BDIO_FCAT_ENTRY_NAMELEN + 1, "saving");

    if(Ptextbuf)
    {
        result <- bdio_fcreate(Ptextbuf, BDIO_FILE_ATTRIB_READ | BDIO_FILE_ATTRIB_WRITE);

        if(!result)
        {
            fHandleOut <- bdio_fbinopenw(Ptextbuf, BDIO_FOPEN_MODE_BUFFERED);
            result <- fHandleOut;

            if(fHandleOut < BDIO_FOPEN_FNAME_NOTFOUND)
            {
                saveLines(PtextedVars, fHandleOut, Ptextbuf);
                bdio_fclose(fHandleOut);
                result <- 0;
            }
        }

        mfree(Ptextbuf);

        if(result)
        {
            bdio_printexecres(result);
        }
    }
}

byte readLines(word PtextedVars, byte fHandleIn, word Pbuf)
{
    //file format: records "<line number> <text>" ended by CHAR_LF, NULLCHAR after the last one
    //records are parsed while the chunks are read, so they may span chunk boundaries
    //textLen is 0 while the line number is parsed, the text is stored from Pline + 1
    word Pline;
    word count;
    word i;
    word lineNumber;
    byte char;
    byte digits;
    byte textLen;
    byte reading;

    Pline <- Pbuf + BDIO_SECTBUF_LEN;
    lineNumber <- 0;
    digits <- 0;
    textLen <- 0;
    reading <- 1;

    while(reading)
    {
        count <- bdio_fbinbufread(fHandleIn, Pbuf, BDIO_SECTBUF_LEN);
        reading <- count;
        i <- 0;

        while(reading && (i < count))
        {
            char <- peek8(Pbuf + i);

            if((char = NULLCHAR) || (char = CHAR_LF))
            {
                //records without a valid line number or without text are skipped
                if(digits && (textLen > 1))
                {
                    poke8(Pline + textLen, NULLCHAR);
                    insertLineBuf(Pline + 1, PtextedVars, lineNumber);
                }

                reading <- char;
                lineNumber <- 0;
                digits <- 0;
                textLen <- 0;
            }
            else
            {
                if(textLen)
                {
                    //longer text is truncated
                    if(textLen <= MAXLINELENGTH)
                    {
                        poke8(Pline + textLen, char);
                        textLen <- textLen + 1;
                    }
                }
                else
                {
                    textLen <- 1;

                    if(char != ' ')
                    {
                        char <- char - '0';

                        if((char > 9) || (lineNumber > 6553) || ((lineNumber = 6553) && (char > 5)))
                        {
                            digits <- 0;
                        }
                        else
                        {
                            lineNumber <- lineNumber * 10 + char;
                            digits <- 1;
                            textLen <- 0;
                        }
                    }
                }
            }

            i <- i + 1;
        }
    }

    printf("%w lines loaded%n", #PtextedVars);
}

byte loadFile(word PinputBuf, word PtextedVars)
{
    word Pbuf;
    word PcurrentLine;
    word PnextLine;
    byte fHandleIn;

    //chunk buffer followed by the line buffer, the file name goes first
    Pbuf <- fileArg(PinputBuf, BDIO_SECTBUF_LEN + MAXLINELENGTH + 2, "loading");

    if(Pbuf)
    {
        fHandleIn <- bdio_fbinopenr(Pbuf, BDIO_FOPEN_MODE_BUFFERED);

        if(fHandleIn < BDIO_FOPEN_FNAME_NOTFOUND)
        {
            //load replaces the buffer, but only once the file is open
            PcurrentLine <- #(PtextedVars + TEVARS_PFIRSTLINE);
            while(PcurrentLine)
            {
                PnextLine <- #(PcurrentLine + TELINE_PNEXT);
                mfree(PcurrentLine);
                PcurrentLine <- PnextLine;
            }
            //TEVARS_TOTALLINES and TEVARS_PFIRSTLINE
            mzero(PtextedVars, 4);

            readLines(PtextedVars, fHandleIn, Pbuf);

            bdio_fclose(fHandleIn);
        }
        else
        {
            bdio_printexecres(fHandleIn);
        }

        mfree(Pbuf);
    }
}

byte mainLoop(word PinputBuf, word PtextedVars) 
{
    byte choice;
    byte continue;
    byte knownCommand;

    continue <- 1;
    
    while(continue) {
        puts("texted>");
        readsn(PinputBuf, MAXLINELENGTH - 1);

        choice <- peek8(PinputBuf);
        choice <- upchar(choice);
        knownCommand <- 0;

        if(choice = 'I') {
            insertLines(PinputBuf, PtextedVars);
            knownCommand <- 1;
        }

        if(choice = 'P') {
            printLines(PinputBuf, PtextedVars);
            knownCommand <- 1;
        }

        if(choice = 'D') {
            deleteLines(PinputBuf, PtextedVars);
            knownCommand <- 1;
        }

        if(choice = 'M') {
            memStat(PinputBuf, PtextedVars);
            knownCommand <- 1;
        }

        if(choice = 'S') {
            saveFile(PinputBuf, PtextedVars);
            knownCommand <- 1;
        }

        if(choice = 'L') {
            loadFile(PinputBuf, PtextedVars);
            knownCommand <- 1;
        }

        if(choice = 'H')
        {
            printf("i <n> <s> - insert new lines starting from line number <n> with step <s>%np <n> <m> - print lines from <n> to <m>%nd <n> <m> - delete lines from <n> to <m>%nl <fname> - loads file (replaces the buffer)%ns <fname> - saves file%nm - memory stats%nh - help%nq - quit%n");
            knownCommand <- 1;
        }

        if(choice = 'Q')
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
    printf("TextEd v1.2%ntype h for help%n");

    PtextedVars <- malloc(TEVARS_SIZE);
    poke16(PtextedVars + TEVARS_TOTALLINES, 0);
    poke16(PtextedVars + TEVARS_PFIRSTLINE, NULL);
    PinputBuf <- malloc(MAXLINELENGTH + 1);

    mainLoop(PinputBuf, PtextedVars);

    mfree(PinputBuf);
    mfree(PtextedVars);
    putsnl("Bye!");
}