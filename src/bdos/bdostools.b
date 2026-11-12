byte bdio_fnormalize(word Pfilenameext, word Pbdiofilename)
{
    byte length;
    byte pointpos;

    mfill(Pbdiofilename, BDIO_FCAT_ENTRY_NAMELEN, 0x20);
    poke8(Pbdiofilename + BDIO_FCAT_ENTRY_NAMELEN, NULLCHAR);

    pointpos <- strnposc(Pfilenameext, '.', BDIO_FCAT_ENTRY_NAMELEN);
    length <- strnlen8(Pfilenameext, BDIO_FCAT_ENTRY_NAMELEN + 1);

    strncpy(Pfilenameext + pointpos + 1, Pbdiofilename + BDIO_FCAT_ENTRY_NAMELEN - 3, length - pointpos - 1);
    strncpy(Pfilenameext, Pbdiofilename, pointpos);

    upstring(Pbdiofilename);
}