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
data_fatal:       .db 'fatal '
data_error:       .db 'error ', 0x00
data_at:          .db ' at ', 0x00
data_helphint:    .db 'type h for help', 0x0a, 0x0d, 0x00
data_help:        .db 'commands:', 0x0a, 0x0d
                  .db ' q - quits the os', 0x0a, 0x0d
                  .db ' h - prints this help', 0x0a, 0x0d, 0x00
;
; subroutines
;=============
; PRINTSTR(*dsdi) - sends chars to printer
; IN: dsdi - address of 0-ended char table
; OUT:   a - set to 0x00
;       ci - set to 0x01
;     dsdi - set to end of char table
printstr:      mov ci, 0x01
printstr_loop: mov a, #dsdi
               jmr z, :printstr_end
               out #ci, a
               cal :inc16
               xor a
               jmr z, :printstr_loop
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
inc16_fail:    mov a, 0x10
               cal :fatal
;=============
; DEC16(dsdi) - decrease 16bit number correctly
; IN:    dsdi - number 16bit, break if lower than 0
; OUT:   dsdi - sub 1
;           a - di - 1 or ds - 1
dec16:         mov a, di
               dec a
               mov di, a
               jmr o, :dec16_ovfl
               ret
dec16_ovfl:    mov a, ds
               dec a
               mov ds, a
               jmr o, :dec16_fail
dec16_ret:     ret
dec16_fail:    mov a, 0x11
               cal :fatal
;=============
; SETVARPARAM16(csci) - stores dsdi value under sys variable var_param16 (2 bytes)
; IN:   csci - value for var_param16
; OUT:  dsdi - unchanged
;       csci - unchanged
;       a    - lo(var_param16) + 1
setvarparam16: psh ds
               psh di
               .mv dsdi, :var_param16
               mov #dsdi, ds
               cal :inc16
               mov #dsdi, di
               pop di
               pop ds
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
add16_cry2err: mov a, 0x12
               cal :fatal
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
sub16_ovr2err: mov a, 0x13
               cal :fatal
;=============
; READSTR(#dsdi, ci) - prints error message and stops
; IN:   dsdi - buffer address for chars
;         ci - length of the buffer (since last char has to be 0x00 we can enter one less)
; OUT:  dsdi - preserved
;         ci - preserved
;         cs - how many chars can we could still add
readstr:       psh ds
               psh di
               psh ci
readstr_loop:  in a, #0x0
               mov cs, a
               sub 0x0d
               jmr z, :readstr_end
               mov a, cs
               sub 0x08
               jmr z, :readstr_del
               mov a, ci
               dec a
               jmr z, :readstr_loop
               mov ci, a
               mov #dsdi, cs
               cal :inc16
               mov a, 0x01
               out #a, cs
               jmr nz, :readstr_loop
readstr_del:   pop a
               psh a
               sub ci
               jmr z, :readstr_loop
               mov a, ci
               inc a
               mov ci, a
               cal :dec16
               xor a
               mov #dsdi, a
               mov cs, 0x01
               mov a, 0x08
               out #cs, a
               mov a, 0x20
               out #cs, a
               mov a, 0x08
               out #cs, a
               jmr nz, :readstr_loop
readstr_end:   xor a
               mov #dsdi, a
               mov cs, ci
               pop ci
               .mv dsdi, :data_newline
               cal :printstr
               pop di
               pop ds
               ret
;=============
; PARSEHEX4(#dsdi) - parses single char to hex number chars 0-9 and a-z and A-Z are supported
; IN:   dsdi - buffer address for char-hex
; OUT:     a - 0 if ok, 0xff if parse error
;         ci - hexval of a char
parsehex4:     mov a, #dsdi
               mov ci, a
               sub 0x30
               jmr n, :parsehex4_err
               mov a, ci
               sub 0x39
               jmr nz, :parsehex4_af
parsehex4_09:  mov a, ci
               sub 0x30
               mov ci, a
               xor a
               ret
parsehex4_af:  mov a, ci
               cal :upchar
               mov ci, a
               sub 0x46
               jmr nz, :parsehex4_err
               mov a, ci
               sub 0x37
               mov ci, a
               xor a
               ret
parsehex4_err: mov a, 0xff
               ret
;=============
; PARSEHEX8(#dsdi) - parses two char to hex number
; IN:   dsdi - buffer address for char
; OUT:    a - success = 0 or >0 error
;        ci - hex value for byte
;      dsdi - moved + 2 if ok
;        cs - rubbish
parsehex8:     cal :parsehex4
               jmr nz, :parsehex8_err
               mov cs, ci
               cal :inc16
               cal :parsehex4
               jmr nz, :parsehex8_err
               cal :inc16
               mov a, cs
               shl 0x04
               and 0xf0
               or  ci
               mov ci, a
parsehex8_err: ret
;=============
; PARSEHEX16(#dsdi) - parses four char to hex number
; IN:   dsdi - buffer address for char
; OUT:  csci - hex value for value
;          a - success = 0 or error code
;       dsdi - moved + 4 if ok
parsehex16:    cal :parsehex8
               jmr nz, :parsehex16_end
               mov cs, ci
               cal :parsehex8
               jmr nz, :parsehex16_end
parsehex16_end:ret
;=============
; UPCHAR(a) - if a is an a-z char returns A-Z
; IN:     a - char code
; OUT:    a - char code A-Z or same
;         ci - old a val
upchar:        mov ci, a
               sub 0x7a
               jmr no, :upchar_skip
               mov a, ci
               sub 0x61
               jmr o, :upchar_skip
               add 0x41
               ret
upchar_skip:   mov a, ci
               ret
;=============
; NEXTWORD(dsdi) - moves to the end of current word
; IN:     dsdi - char buffer address
; OUT:    dsdi - address of the next word or end of buffer
;            a - >0 if next word exist
nextword:      mov a, #dsdi
               jmr z, :nextword_eof
               sub 0x20
               jmr z, :nextword_eatws
               cal :inc16
               xor a
               jmr z, :nextword
nextword_eatws:cal :inc16
               mov a, #dsdi
               jmr z, :nextword_eof
               sub 0x20
               jmr z, :nextword_eatws
               mov a, 0x01
nextword_eof:  ret
;=============
; FATAL(a) - prints error message and stops
; IN:   a - error code
;   stack - as error address
; OUT:  KILL, messed stack
;
fatal:         psh a
               .mv dsdi, :data_newline
               cal :printstr
               .mv dsdi, :data_fatal
               cal :printstr
               pop a
               cal :printhex8
               .mv dsdi, :data_at
               cal :printstr
               pop ci
               pop cs
               cal :printhex16
               kil
;=============
; ERROR(a)  - prints error message and continues
; IN:     a - error code
; OUT: dsdi - preserved
;      csci - preserved
error:         psh ds
               psh di
               psh cs
               psh ci
               psh a
               .mv dsdi, :data_newline
               cal :printstr
               .mv dsdi, :data_error
               cal :printstr
               pop a
               cal :printhex8
               .mv dsdi, :data_newline
               cal :printstr
               pop ci
               pop cs
               pop di
               pop ds
               ret
;=============
; EXEC_DUMP(#dsdi)  - executes dump command
; IN:  dsdi - address of var_promptbuf
; OUT: rubbish
exec_dump:     cal :nextword
               jmr z, :exec_dump_nar1
               cal :parsehex16
               kil
               jmr nz, :exec_dump_per1
               psh cs
               psh ci
               cal :nextword
               jmr z, :exec_dump_nar2
               cal :parsehex16
               jmr nz, :exec_dump_per2
               pop di
               pop ds
exec_dump_prnt:mov a, 0x10
               psh a
exec_dump_loop:mov a, #dsdi
               psh cs
               psh ci
               cal :printhex8
               pop ci
               pop cs
               cal :dec16
               mov a, cs
               and ci
               jmr z,:exec_dump_end
               psh cs
               psh ci
               mov cs, ds
               mov ci, di
               cal :inc16
               mov ds, cs
               mov di, ci
               pop ci
               pop cs
               pop a
               dec a
               jmr z,:exec_dump_nl
               psh a
               jmr nz, :exec_dump_loop
exec_dump_nl:  mov a, 0x10
               psh a
               psh cs
               mov cs, 0x01
               mov a, 0x0a
               out #cs, a
               mov a, 0x0d
               out #cs, a
               pop cs
               jmr nz, :exec_dump_loop
               ret
exec_dump_nar1:mov a, 0x02
               jmr nz, :exec_dump_err
exec_dump_nar2:mov a, 0x04
               jmr nz, :exec_dump_err
exec_dump_per1:mov a, 0x03
               jmr nz, :exec_dump_err
exec_dump_per2:mov a, 0x05
               jmr nz, :exec_dump_err
exec_dump_err: cal :error
exec_dump_end: pop a
               ret               
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
               mov ci, 0x21
               cal :readstr
os_parse:      mov a, #dsdi
               cal :upchar
               mov #dsdi, a
               mov ci, a
               sub 0x51
               jmr nz, :os_parse_notq
os_exec_q:     mov a, 0xf0
               cal :fatal
os_parse_notq: mov a, ci
               sub 0x48
               jmr nz, :os_parse_noth
os_exec_help:  .mv dsdi, :data_help
               cal :printstr
               .mv csci, :os_goto_parse
               xor a
               jmp z, csci
os_parse_noth: mov a, ci
               sub 0x44
               jmr nz, :os_parse_notd
os_exec_dump:  cal :exec_dump
               .mv csci, :os_goto_parse
               xor a
               jmp z, csci
os_parse_notd: mov a, ci
               sub 0x50
               jmr nz, :os_parse_unrec
os_exec_print: nop            
os_parse_unrec:mov a, 0x01
               cal :error               
os_goto_parse: .mv csci, :os_prompt
               xor a
               jmp z, csci
os_end:        mov a, 0xff
               cal :fatal
;
; os variables
;
var_param16:   .db 0x00, 0x00
var_user_mem:  .db 0x00, 0x00
var_top_mem:   .db 0x00, 0x00
var_promptbuf: .db 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
               .db 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
               .db 0x00
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
