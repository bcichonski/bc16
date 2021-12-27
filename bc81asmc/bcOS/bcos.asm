; bc16 Operation System version 0.1.20211221
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
data_from:        .db 'from ', 0x0a, 0x0d, 0x00
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
; PRINTHEX8(a) - prints hex number 
; IN:    a - number to print
; OUT:   a - set to lower half
;       cs - set to 1
;       ci - set to a
printhex8:     mov ci, a
               mov cs, 0x01
               shr 0x04
               and 0x0f
               add 0x30
               out #cs, a
               mov a, ci
               and 0x0f
               add 0x30
               out #cs, a
               ret
;=============
; SETVARPARAM16(dsdi) - stores dsdi value under sys variable var_param16 (2 bytes)
;                       because uses 8bit inc address must be in same ds segment
;                       this code guards against it
; IN:   dsdi - value for var_param16
; OUT:  csci - #var_param16 + 1
;       dsdi - unchanged
;       a    - lo(var_param16) + 1
setvarparam16: .mv csci, :var_param16
               mov #csci, ds
               mov a, ci
               inc a
               jmr c, :setvarp16_fail
               mov ci, a
               mov #csci, di
setvarp16_ok:  ret
setvarp16_fail:kil
;=============
; POKE16(#dsdi, var_param16) - stores dsdi value under csci address (2 bytes)
;                       because uses 8bit inc address must be in same ds segment
;                       this code guards against it
; IN:   dsdi - address to store
;       var_param16 - value to store
; OUT:  csci - #var_param16 + 1
;       dsdi - address to store + 1
;       a    - lo(val(var_param16))
poke16:        .mv csci, :var_param16
               mov a, #csci
               mov #dsdi, a
               mov a, ci
               inc a
               jmr c, :poke16_fail
               mov ci, a
               mov a, di
               inc a
               jmr c, :poke16_fail
               mov di, a
               mov a, #csci
               mov #dsdi, a
poke16_ok:     ret             
poke16_fail:   kil
;
; main code
; 1.initialize os
init:          .mv dsdi, :user_mem
               .mv csci, :setvarparam16
               cal csci
               .mv dsdi, :var_user_mem
               .mv csci, :poke16
               cal csci
; 2.write greetings
hello:         .mv dsdi, :data_os
               .mv csci, :printstr
               cal csci
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
