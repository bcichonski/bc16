; bc16 Operation System version 0.1.20211228
;
               .org 0x0000
start:         .mv csci, :init
               jmp z, csci
;
; data
;
data_os:          .db 'bcOS 0.1'
data_newline:     .db 0x0a, 0x0d, 0x00
data_free:        .db 'free ', 0x00
data_from:        .db 'from ', 0x00
data_to:          .db ' to ', 0x00
data_prompt:      .db '>', 0x00
;
; subroutines
;=============
; PRINTSTR(*dsdi) - sends chars to printer
; IN: dsdi - address of 0-ended char table, must start and end in the same ds segment!
; OUT:   a - set to 0x00
;       ci - set to 0x01
;     dsdi - set to end of char table
printstr:      mov ci, 0x01
printstr_loop: mov a, #dsdi
               jmr z, :printstr_end
               out #ci, a
               mov a, di
               inc a
               mov di, a
               jmr nz, :printstr_loop
printstr_end:  ret
;=============
; PRINTHEX4(a) - prints hex number from 0 to f
; IN:    a - number to print
; OUT:   a - unchanged      10 -> 0 -> 41
;       cs - set to 1
printhex4:     mov cs, 0x01
               psh a
               sub 0x0a
               jmr nc, :printhex4_af
printhex4_09:  pop a
               add 0x30
               out #cs, a
               ret
printhex4_af:  pop a
               add 0x37
               out #cs, a
               ret
;=============
; PRINTHEX8(a) - prints hex number 
; IN:    a - number to print
; OUT:   a - set to lower half
;       cs - set to 1
;       ci - set to a
;     dsdi - unchanged
printhex8:     mov ci, a
               shr 0x04
               cal :printhex4
               mov a, ci
               and 0x0f
               cal :printhex4
               ret
;=============
; PRINTHEX16(csci) - prints hex number 4 digits
; IN:    csci - hex number 4 digits
; OUT:   csci - unchanged
;           a - ci
printhex16:    mov a, cs
               cal :printhex8
               mov a, ci
               cal :printhex8
               ret
;=============
; INC16(dsdi) - increase 16bit number correctly
; IN:    dsdi - number 16bit, break if exceeds 16bit
; OUT:   dsdi - add 1
;           a - di + 1 or ds + 1
inc16:         mov a, di
               inc a
               mov a, di
               jmr c, :inc16_carry
               ret
inc16_carry:   mov a, ds
               inc a
               mov ds, a
               jmr c, :inc16_fail
inc16_ret:     ret
inc16_fail:    kil
;=============
; SETVARPARAM16(csci) - stores dsdi value under sys variable var_param16 (2 bytes)
; IN:   csci - value for var_param16
; OUT:  dsdi - #var_param16 + 1
;       csci - unchanged
;       a    - lo(var_param16) + 1
setvarparam16: .mv dsdi, :var_param16
               mov #dsdi, ds
               cal :inc16
               mov #dsdi, di
               ret
;=============
; POKE16(#dsdi, csci) - stores csci value under #dsdi address (2 bytes)
; IN:   dsdi - address to store
;       csci - value to store
; OUT:  dsdi - address to store + 1
;       csci - unchanged
;       a    - ci
poke16:        mov #dsdi, cs
               cal :inc16
               mov #dsdi, ci
poke16_ok:     ret             
;=============
; PEEK16(#dsdi) - returns value under dsdi address (2 bytes)
; IN:   dsdi - address to read
; OUT:  dsdi - address to read + 1
;       csci - value
;       a    - ci
peek16:        mov cs, #dsdi
               cal :inc16
               mov ci, #dsdi
peek16_ok:     ret
;=============
; ADD16(csci,dsdi) - returns value under csci address (2 bytes)
;                 because uses 8bit inc address must be in same ds segment
;                 this code guards against it
; IN:   csci - address to read
; OUT:  dsdi - value from #csci
;       dsdi - address to store + 1
;       a    - lo(val(var_param16))
add16:         mov ds, #csci
               mov a, ci
               inc a
               jmr c, :add16_fail
               mov ci, a
               mov di, #csci
add16_ok:      ret             
add16_fail:    kil
;
; main code
; 1.initialize os
init:          mov cs, ss
               mov ci, si
               .mv dsdi, :var_top_mem
               cal :poke16
               .mv csci, :user_mem
               .mv dsdi, :var_user_mem
               cal :poke16
; 2.write greetings
hello:         .mv dsdi, :data_os
               cal :printstr
               .mv dsdi, :data_from
               cal :printstr
               .mv dsdi, :var_user_mem
               cal :peek16
               cal :printhex16
               .mv dsdi, :data_to
               cal :printstr
               .mv dsdi, :var_top_mem
               cal :peek16
               cal :printhex16
eos:           kil
;
; os variables
;
var_param16:   .db 0x00, 0x00
var_user_mem:  .db 0x00, 0x00
var_top_mem:   .db 0x00, 0x00
var_promptbuf: .db 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
               .db 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
user_mem:      nop
; 3.write prompt
; 4.read command
; 5.parse & exec command
; 6.goto 3
;
;memory map
;0x0000-0x????:eos - bcos rom
;0x????:eos        - bcos sys variables
;0x????:eos+1      - 
;... stack going ^
;0x3fff
