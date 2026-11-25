#include bdosargs.h

// bdosargs.b - shared command-line argument helpers of the bdos utilities (issue 43, D10).
//
// Opt-in include (D7): it contains no #include but its own header bdosargs.h. Include it after its dependencies:
//   #include std.b
//   #include bdosh.b
//   #include strings.b
//   #include bdostools.b
//   #include bdosargs.b
// The compiler links every function of every include (no dead-code elimination, #16),
// so a tool pays for all helpers below even when it calls only some of them.
//
// The command line is upper-cased by the caller (upstring) before any helper is used.
//
// getdriveletter(drive)        "A", "B" or "?" for any other drive.
// getdrive(Pword)              word starting with "A:" -> BDIO_DRIVEA | DRIVEPRESENT,
//                              "B:" -> BDIO_DRIVEB | DRIVEPRESENT, else bdio_getdrive()
//                              without the flag. Storing it in a byte drops the flag.
// changeDriveIfNeeded(current, target, silent)
//                              switches to target when it differs from current;
//                              returns the drive that is now active.
// getswitch(Pword, Pletters)   1-based position of the word's second character in the
//                              NUL-terminated letter list when the word starts with '-',
//                              else 0. Only the first two characters are looked at; the
//                              NUL terminator never matches (a bare "-" gives 0).
// argfile(Pword, Pcatname)     parses one [d:]name.ext word: drive via getdrive, skips the
//                              d: prefix, terminates the word in place at its first space,
//                              writes the 11-character catalog name to Pcatname with
//                              bdio_fnormalize; returns the getdrive result. Take the address
//                              of a later word with strnextword BEFORE calling argfile.
// printusage(Ptitle, Pline1, Pline2)
//                              prints each non-zero string followed by a newline, title
//                              first; 0 skips a line.

word getdriveletter(byte drive)
{
    word driveLetter;
    driveLetter <- "?";
    if(drive = BDIO_DRIVEA)
    {
        driveLetter <- "A";
    }
    else
    {
        if(drive = BDIO_DRIVEB)
        {
            driveLetter <- "B";
        }
    }

    return driveLetter;
}

word getdrive(word Pword)
{
    word result;

    if(strncmp(Pword, "A:", 2) = STRCMP_EQ)
    {
        result <- BDIO_DRIVEA | DRIVEPRESENT;
    }
    else
    {
        if(strncmp(Pword, "B:", 2) = STRCMP_EQ)
        {
            result <- BDIO_DRIVEB | DRIVEPRESENT;
        }
        else
        {
            result <- bdio_getdrive();
        }
    }
    return result;
}

byte changeDriveIfNeeded(byte currentDrive, byte targetDrive, byte silent)
{
    if(currentDrive != targetDrive)
    {
        bdio_setdrive(targetDrive, silent);
        currentDrive <- targetDrive;
    }
    return currentDrive;
}

byte getswitch(word Pword, word Pletters)
{
    byte result;
    byte option;
    byte letter;
    byte pos;

    result <- 0;

    if(peek8(Pword) = '-')
    {
        option <- peek8(Pword + 1);
        pos <- 1;
        letter <- peek8(Pletters);

        while(letter && (result = 0))
        {
            if(letter = option)
            {
                result <- pos;
            }

            pos <- pos + 1;
            Pletters <- Pletters + 1;
            letter <- peek8(Pletters);
        }
    }

    return result;
}

word argfile(word Pword, word Pcatname)
{
    word result;
    word Pend;
    byte char;

    result <- getdrive(Pword);
    if(result & DRIVEPRESENT)
    {
        Pword <- Pword + 2;
    }

    Pend <- Pword;
    char <- peek8(Pend);
    while(char && (char != ' '))
    {
        Pend <- Pend + 1;
        char <- peek8(Pend);
    }
    poke8(Pend, NULLCHAR);

    bdio_fnormalize(Pword, Pcatname);

    return result;
}

byte printusage(word Ptitle, word Pline1, word Pline2)
{
    if(Ptitle)
    {
        putsnl(Ptitle);
    }
    if(Pline1)
    {
        putsnl(Pline1);
    }
    if(Pline2)
    {
        putsnl(Pline2);
    }
}
