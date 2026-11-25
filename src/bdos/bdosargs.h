#define DRIVEPRESENT 0x0100

word getdriveletter(byte drive)
word getdrive(word Pword)
byte changeDriveIfNeeded(byte currentDrive, byte targetDrive, byte silent)
byte getswitch(word Pword, word Pletters)
word argfile(word Pword, word Pcatname)
byte printusage(word Ptitle, word Pline1, word Pline2)
