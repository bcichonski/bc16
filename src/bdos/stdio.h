#define PRINTF_FORMATCHAR 0x25
#define PRINTF_NEWLINECHAR 'n'
#define PRINTF_HEX8 'x'
#define PRINTF_HEX16 'w'
#define PRINTF_STRING 's'

byte putdigit(byte digit)
byte putb(byte value)
byte putc(byte char)
byte putw(word value)
byte putwnl(word value)
byte putnl()
byte puts(word Pstr)
byte putsnl(word Pstr)
byte readsn(word Pbuf, byte maxlen)
byte putdecw(word value)
byte putdecwnl(word value)
byte printf(word PformatStr)***
