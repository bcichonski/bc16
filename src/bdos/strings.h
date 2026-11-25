#define NULLCHAR 0x00
#define STRCMP_GT 0xf0
#define STRCMP_LT 0x0f
#define STRCMP_EQ 0x00
#define STRPOS_NOTFOUND 0xffff

byte strpeek8(word Paddr)
byte strpoke8(word Paddr, byte value)
byte strnlen8(word Pstring, byte maxLength)
byte strcpy(word Pstring, word Ptarget)
byte strncpy(word Pstring, word Ptarget, byte len)
byte strncmp(word Pstring1, word Pstring2, word maxlen)
word strnposc(word Pstring, byte char, word maxlen)
byte upchar(byte char)
byte upstring(word Pstring)
word strnextword(word Pstring)
byte strndecw(word value, word Pbuf, byte maxlen)
