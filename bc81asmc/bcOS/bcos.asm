; bc16 Operation System version 0.1.20211228
;
               .org 0x0000
os_start:      .mv csci, :os_init
               jmp z, csci
;
; data
;
data_os:          .db 'bcOS 0.2'
data_newline:     .db 0x0a, 0x0d, 0x00
data_free:        .db 'free ', 0x00
data_from:        .db ' from ', 0x00
data_to:          .db ' to ', 0x00
data_prompt:      .db '> ', 0x00
data_error:       .db 'error ', 0x00
data_at:          .db ' at ', 0x00
data_helphint:    .db 'type h for help', 0x0a, 0x0d, 0x00
data_help:        .db 'supported commands:', 0x0a, 0x0d
                  .db 'h - prints this help', 0x0a, 0x0d, 0x00
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
               jmr no, :printhex4_af
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
               psh ci
               cal :printhex8
               pop a
               cal :printhex8
               ret
;=============
; INC16(dsdi) - increase 16bit number correctly
; IN:    dsdi - number 16bit, break if exceeds 16bit
; OUT:   dsdi - add 1
;           a - di + 1 or ds + 1
inc16:         mov a, di
               inc a
               mov di, a
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
;                    return os error 0x10 in case of overflow                
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  csci - sum of csci and dsdi
;       a    - rubbish
add16:         mov a, ci
               add di
               mov ci, a
               jmr c, :add16_carry1
               mov a, cs
add16_cry_nxt: add ds
               mov cs, a
               jmr c, :add16_cry2err
add16_ok:      ret
add16_carry1:  mov a, cs
               inc a
               jmr nc, :add16_cry_nxt
add16_cry2err: mov a, 0x10
               cal :error
;=============
; SUB16(csci,dsdi) - returns value under csci address (2 bytes) 
;                    return os error 0x11 in case of overflow                
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  csci - substracts dsdi from csci
;       a    - rubbish
sub16:         mov a, ci
               sub di
               mov ci, a
               jmr o, :sub16_ovr1
               mov a, cs
sub16_crynxt:  sub ds
               mov cs, a
               jmr o, :sub16_ovr2err
sub16_ok:      ret
sub16_ovr1:    mov a, cs
               dec a
               jmr no, :sub16_crynxt
sub16_ovr2err: mov a, 0x11
               cal :error
;=============
; READSTR(#dsdi, ci) - prints error message and stops
; IN:   dsdi - buffer address for chars
;         ci - length of the buffer
; OUT:  
readstr:       mov cs, 0x00
               in a, #cs
;=============
; ERROR(a) - prints error message and stops
; IN:   a - error code
;   stack - as error address
; OUT:  KILL, messed stack
;
error:         psh a
               .mv dsdi, :data_newline
               cal :printstr
               .mv dsdi, :data_error
               cal :printstr
               pop a
               cal :printhex8
               .mv dsdi, :data_at
               cal :printstr
               pop ci
               pop cs
               cal :printhex16
               kil
; main code
; 1.initialize os
os_init:       mov cs, ss
               mov ci, si
               .mv dsdi, :var_top_mem
               cal :poke16
               .mv csci, :user_mem
               .mv dsdi, :var_user_mem
               cal :poke16
; 2.write greetings
os_hello:      .mv dsdi, :data_os
               cal :printstr
               .mv dsdi, :data_free
               cal :printstr
               .mv dsdi, :var_user_mem
               cal :peek16
               psh cs
               psh ci
               .mv dsdi, :var_top_mem
               cal :peek16
               pop di
               pop ds
               psh cs
               psh ci
               psh ds
               psh di
               cal :sub16
               cal :printhex16
               .mv dsdi, :data_from
               cal :printstr
               pop ci
               pop cs
               cal :printhex16
               .mv dsdi, :data_to
               cal :printstr
               pop ci
               pop cs
               cal :printhex16
               .mv dsdi, :data_newline
               cal :printstr
               .mv dsdi, :data_helphint
               cal :printstr
os_prompt:     .mv dsdi, :data_prompt
               cal :printstr
               .mv dsdi, :var_promptbuf
               mov ci, 0x20
;               cal :readstr
os_end:        mov a, 0xff
               cal :error
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
