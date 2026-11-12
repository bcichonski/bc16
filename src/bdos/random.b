word random(word max)
{
    //random number from bdos: 0..max-1, or the whole 16-bit word when max = 0
    //needs bdosh.b included before this file

    return bdio_call(BDIO_RANDOM, max, 0);
}
