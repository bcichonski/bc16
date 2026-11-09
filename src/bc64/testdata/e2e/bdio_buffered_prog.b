#code 0x6000
#heap 0xa000

#include std.b
#include bdosh.b

#define SRC 0xb000
#define DST 0xc000
#define LEN 589
#define PAD 51

#define WBAD 0xb800
#define RBAD 0xb801

word wr(byte h, word off, word n)
{
    word r;
    r <- bdio_fbinbufwrite(h, SRC + off, n);
    if(r != n)
    {
        putsnl("write bad");
        putwnl(n);
        putwnl(r);
        poke8(WBAD, peek8(WBAD) + 1);
    }
    return off + n;
}

word rd(byte h, word off, word n)
{
    word r;
    r <- bdio_fbinbufread(h, DST + off, n);
    if(r != n)
    {
        putsnl("read bad");
        putwnl(n);
        putwnl(r);
        poke8(RBAD, peek8(RBAD) + 1);
    }
    return off + n;
}

byte main()
{
    word i;
    word off;
    word r;
    word bad;
    byte h;

    poke8(WBAD, 0);
    poke8(RBAD, 0);
    i <- 0;
    while(i < LEN)
    {
        poke8(SRC + i, (7 * i + 3) & 0xff);
        i <- i + 1;
    }
    mfill(DST, 0x0300, 0xaa);

    bdio_fcreate("BUFTEST DAT", BDIO_FILE_ATTRIB_READ | BDIO_FILE_ATTRIB_WRITE);
    h <- bdio_fbinopenw("BUFTEST DAT", BDIO_FOPEN_MODE_BUFFERED);
    off <- 0;
    off <- wr(h, off, 1);
    off <- wr(h, off, 127);
    off <- wr(h, off, 128);
    off <- wr(h, off, 60);
    off <- wr(h, off, 200);
    off <- wr(h, off, 3);
    off <- wr(h, off, 70);
    bdio_fclose(h);
    if(peek8(WBAD) = 0)
    {
        putsnl("write ok");
    }

    h <- bdio_fbinopenr("BUFTEST DAT", BDIO_FOPEN_MODE_BUFFERED);
    off <- 0;
    off <- rd(h, off, 128);
    off <- rd(h, off, 1);
    off <- rd(h, off, 50);
    off <- rd(h, off, 127);
    off <- rd(h, off, 100);
    off <- rd(h, off, 128);
    off <- rd(h, off, 55);

    bad <- 0;
    i <- 0;
    while(i < LEN)
    {
        if(peek8(SRC + i) != peek8(DST + i))
        {
            if(bad < 4)
            {
                putsnl("mismatch");
                putwnl(i);
                putwnl(peek8(SRC + i));
                putwnl(peek8(DST + i));
            }
            bad <- bad + 1;
        }
        i <- i + 1;
    }
    if(peek8(RBAD) = 0)
    {
        if(bad = 0)
        {
            putsnl("read ok");
        }
    }

    r <- bdio_fbinbufread(h, DST + LEN, 128);
    bad <- 0;
    i <- LEN;
    while(i < LEN + PAD)
    {
        if(peek8(DST + i) != 0)
        {
            bad <- bad + 1;
        }
        i <- i + 1;
    }
    if(r != PAD)
    {
        putsnl("tail bad");
        putwnl(r);
        bad <- bad + 1;
    }
    r <- bdio_fbinbufread(h, DST + 0x0280, 128);
    if(r != 0)
    {
        putsnl("eof bad");
        putwnl(r);
        bad <- bad + 1;
    }
    if(bad = 0)
    {
        putsnl("eof ok");
    }
    bdio_fclose(h);

    h <- bdio_fbinopenr("BUFTEST DAT", BDIO_FOPEN_MODE_SECTOR);
    r <- bdio_fbinbufread(h, DST, 10);
    if(r = 0)
    {
        putsnl("nonbuf ok");
    }
    else
    {
        putsnl("nonbuf bad");
        putwnl(r);
    }
    bdio_fclose(h);

    h <- bdio_fbinopenr("NOPE    DAT", BDIO_FOPEN_MODE_BUFFERED);
    if(h = 0xe0)
    {
        putsnl("missing ok");
    }
    else
    {
        putsnl("missing bad");
        putwnl(h);
    }
}
