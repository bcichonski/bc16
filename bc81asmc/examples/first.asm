      org 0x0100
init: inc a
      dec a
      nop
      nop
do:   mov ss, 0xff
      mov di, ss
      mov a, #csci
