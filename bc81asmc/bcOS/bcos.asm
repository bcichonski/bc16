; bc16 Operation System version 0.1.20211221
;
               .org 0x0000
start:         .mv csci, :init
               jmp z, csci
;
; data
;
data_os:          .db 'bcOS 0.1', 0x00
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
;
; main code
init:          .mv dsdi, :data_os
               .mv csci, :printstr
               cal csci
               kil
; 1.initialize os
; 2.write greetings
; 3.write prompt
; 4.read command
; 5.parse & exec command
; 6.goto 3
