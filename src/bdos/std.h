#define TRUE 0x01
#define FALSE 0x00

byte peek8(word Paddr)
byte peek16(word Paddr)
byte poke8(word Paddr, byte value)
byte poke16(word Paddr, word value)
word parsedecw(word Pbuf, byte maxlen)
word mfill(word Paddr, word length, byte value)
word mzero(word Paddr, word length)
word memcpy(word Psource, word Pdesc, word len)
