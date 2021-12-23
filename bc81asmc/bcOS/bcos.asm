; bc16 Operation System version 0.1.20211221
;
            .org 0x0000
start:      nop ;.mvl csci, :init
            ;jmp csci
; data
d_os:       .db 'bcOS 0.1', 0x00
d_prompt:   .db '>', 0x00
; subroutines
; main code
init:       kil
; 1.initialize os
; 2.write greetings
; 3.write prompt
; 4.read command
; 5.parse & exec command
; 6.goto 3
