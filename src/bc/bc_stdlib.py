stdlib_template = """
;>>>>>>>>>>COMPILER ASM STDLIB for BCOS v1.0 on BC16 v1.0<<<<<<<<<<<<<
            mov a, 0xff
            mov a, 0xff
            mov a, 0xff
            mov a, 0xff
;=============
; FATAL(a) - prints error message and stops
; IN:   a - error code
;   stack - as error address
; OUT:  KILL, messed stack
            .def fatal, 0x04ea
;=============
; PRINTHEX4(a) - prints hex number from 0 to f
; IN:    a - number to print
; OUT:   a - unchanged      10 -> 0 -> 41
;       cs - set to 1
            .def printhex4, 0x0349
;=============
; PRINTHEX8(a) - prints hex number 
; IN:    a - number to print
; OUT:   a - set to lower half
;     csci - unchanged
;     dsdi - unchanged
            .def printhex8, 0x035c
;=============
; PRINTHEX16(csci) - prints hex number 4 digits
; IN:    csci - hex number 4 digits
; OUT:   csci - unchanged
;           a - ci
            .def printhex16, 0x036f
;=============
; INC16(dsdi) - increase 16bit number correctly
; IN:    dsdi - number 16bit, break if exceeds 16bit
; OUT:   dsdi - add 1
;           a - di + 1 or ds + 1
            .def inc16, 0x037a
;=============
; DEC16(dsdi) - decrease 16bit number correctly
; IN:    dsdi - number 16bit, break if lower than 0
; OUT:   dsdi - sub 1
;           a - di - 1 or ds - 1
            .def dec16, 0x038f
;=============
; POKE16(#dsdi, csci) - stores csci value under #dsdi address (2 bytes)
; IN:   dsdi - address to store
;       csci - value to store
; OUT:  dsdi - address to store + 1
;       csci - unchanged
;       a    - rubbish
            .def poke16, 0x03b0            
;=============
; PEEK16(#dsdi) - returns value under dsdi address (2 bytes)
; IN:   dsdi - address to read
; OUT:  dsdi - address to read + 1
;       csci - value
;       a    - rubbish
            .def peek16, 0x03b8
;=============
; ADD16(csci,dsdi) - returns value
;                    return os error 0x12 in case of overflow                
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  csci - sum of csci and dsdi
;       a    - rubbish
            .def add16, 0x03c0
;=============
; SUB16(csci,dsdi) - returns value 
;                    return os error 0x13 in case of overflow                
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  csci - substracts dsdi from csci
;       a    - rubbish
            .def sub16, 0x03db
;=============
; MUL16(csci,dsdi) - returns value 
;                    return os error 0x12 in case of overflow                
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  csci - mutiplies csci by dsdi
;       dsdi - unchanged
;       a    - rubbish
mul16:       psh ds
             psh di
             cal :gteq16
             jmr nz, :mul16_swpskp
             psh cs
             mov cs, ds
             pop ds
             psh ci
             mov ci, di
             pop di
mul16_swpskp:mov a,ds
             or di
             jmr nz,:mul16_isone
             xor a
             mov cs, a
             mov ci, a
             jmr z,:mul16_ret
mul16_isone: mov a, ds
             jmr nz, :mul16_calc
             mov a, di
             dec a
             jmr nz, :mul16_calc
             jmr z, :mul16_ret
mul16_calc:  xor a
             psh a
             psh a
mul16_loop:  mov a, di
             and 0x01
             jmr z, :mul16_by2
             psh cs
             psh ci
mul16_by2:   mov a, cs
             shl 0x01
             mov cs, a
             mov a, ci
             shl 0x01
             jmr no, :mul16_by2nst
             psh a
             mov a, cs
             or 0x01
             mov cs, a
             pop a
mul16_by2nst:mov ci, a
             mov a, di
             shr 0x01
             mov di, a
             mov a, ds
             and 0x01
             jmr z, :mul16_by2nmt
             mov a, di
             or 0x80
             mov di, a
mul16_by2nmt:mov a, ds
             shr 0x01
             mov ds, a
             or  di
             dec a
             jmr nz, :mul16_loop
mul16_addlp: pop di
             pop ds
             mov a, di
             or  ds
             jmr z, :mul16_ret
             cal :add16
             xor a
             jmr z, :mul16_addlp
mul16_ret:   pop di
             pop ds
             ret
;=============
; DIV16(csci,dsdi) - returns value 
;                    return os error 0x13 in case of overflow                
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  csci - divides csci by dsdi
;       dsdi - unchanged
;       a    - rubbish
div16:       psh cs
             psh ci
             mov cs, ds
             mov ci, di
             .mv dsdi, :sys_div16tmp
             cal :poke16
             mov ds, cs
             mov di, ci
             pop ci
             pop cs
             cal :gteq16
             jmr z, :div16_zero
             mov a, 0x80
             and ds
             jmr nz, :div16_one
             xor a
             psh a
             inc a
             psh a
div16_loop:  psh ds
             psh di
             cal :sub16
             pop di
             pop ds
             cal :gteq16
             jmr z, :div16_end
             pop di
             pop ds
             cal :inc16
             psh ds
             psh di
             psh cs
             psh ci
             .mv dsdi, :sys_div16tmp
             cal :peek16
             mov ds, cs
             mov di, ci
             pop ci
             pop cs        
             xor a
             jmr z, :div16_loop
div16_end:   pop ci
             pop cs
             ret          
div16_one:   mov cs, 0x00
             mov ci, 0x01
             jmr nz, :div16_ret
div16_zero:  xor a
             mov cs, a
             mov ci, a
div16_ret:   ret
;=============
; READSTR(#dsdi, ci) - reads characters to the buffer
; IN:   dsdi - buffer address for chars
;         ci - length of the buffer (since last char has to be 0x00 we can enter one less)
; OUT:  dsdi - preserved
;         ci - preserved
;         cs - how many chars can we could still add
            .def readstr, 0x03f6
;=============
; NEXTWORD(dsdi) - moves to the end of current word
; IN:     dsdi - char buffer address
; OUT:    dsdi - address of the next word or end of buffer
;            a - >0 if next word exist
            .def nextword, 0x04b4
;=============
; NEXTVAL8(dsdi) - moves until expected value
; IN:     dsdi - char buffer address
;           ci - expected 8bit value
;           cs - max length to check
; OUT:    dsdi - address of the next byte or end of buffer
;           cs - how much was left to end of buffer
;           ci - unchanged
;            a - >0 if value was found
            .def nextval8, 0x04d1
;=============
; STR_CPY(csci,dsdi)  - copy string from dsdi to csci
; IN: dsdi - source  
;     csci - desc
; OUT: dsdi = source + length + 1
            .def str_cpy, 0x0562
;=============
; STR_LEN8(dsdi)  - length of the string ending with 0x00
; IN: dsdi - source  
;     cs   - max length
; OUT: dsdi - preserved, cs = rubbish, ci = actual length
            .def str_len8, 0x0581
;=============
; PARSEHEX4(#dsdi) - parses single char to hex number chars 0-9 and a-z and A-Z are supported
; IN:   dsdi - buffer address for char-hex
; OUT:     a - 0 if ok, 0xff if parse error
;         ci - hexval of a char
            .def parsehex4, 0x0448
;=============
; PARSEHEX8(#dsdi) - parses two char to hex number
; IN:   dsdi - buffer address for char
; OUT:    a - success = 0 or >0 error
;        ci - hex value for byte
;      dsdi - moved + 2 if ok
            .def parsehex8, 0x0476
;=============
; PARSEHEX16(#dsdi) - parses four char to hex number
; IN:   dsdi - buffer address for char
; OUT:  csci - hex value for value
;          a - success = 0 or error code
;       dsdi - moved + 4 if ok
            .def parsehex16, 0x0497
;=============
; PRINT_NEWLINE - prints new line
; IN:
; OUT:   a - rubbish
            .def print_newline, 0x0323
;=============
; PRINTSTR(*dsdi) - sends chars to printer
; IN: dsdi - address of 0-ended char table
; OUT:   a - set to 0x00
;       ci - set to 0x01
;     dsdi - set to end of char table
            .def printstr, 0x0339
;=============
; GT16(csci,dsdi) - compares csci with dsdi            
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  a - 1 if csci > dsdi
;       a - 0 otherwise
gt16:        mov a, cs
             sub ds
             jmr o, :gt16_false
             jmr nz, :gt16_true
             mov a, ci
             sub di
             jmr o, :gt16_false
             jmr nz, :gt16_true
gt16_false:  xor a
             ret
gt16_true:   mov a, 0x01
             ret
;=============
; GTEQ16(csci,dsdi) - compares csci with dsdi            
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  a - 1 if csci >= dsdi
;       a - 0 otherwise
gteq16:      mov a, cs
             sub ds
             jmr o, :gteq16_false
             jmr nz, :gteq16_true
             mov a, ci
             sub di
             jmr o, :gteq16_false
             jmr nz, :gteq16_true
gteq16_true: mov a, 0x01
             ret
gteq16_false:xor a
             ret
;=============
; EQ16(csci,dsdi) - compares csci with dsdi            
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  a - 1 if csci == dsdi
;       a - 0 otherwise
eq16:       mov a, cs
            sub ds
            jmr nz, :gteq16_false
            mov a, ci
            sub di
            jmr nz, :gteq16_false
eq16_true:  mov a, 0x01
            ret
eq16_false: xor a
            ret
;=============
; STACKOFFSCALC(csci,a) - modifies SYS_STACKHEAD by csci and stores new value back in csci
; IN: csci - value to increase
;        a - 0x00 - add
;            0x01 - sub
; OUT:csci - value of SYS_STACKHEAD with offset
;     dsdi - address of SYS_STACKHEAD
;        a - rubbish
stackoffscalc: psh a
               psh cs
               psh ci
               .mv dsdi, :{0}
               cal :peek16
               pop di
               pop ds
               pop a
               and a
               jmr nz, :stoffclc_sub
               cal :add16
               xor a
               jmr z, :stoffclc_end
stoffclc_sub:  cal :sub16  
stoffclc_end:  .mv dsdi, :{0}
               ret
;=============
; STACKOFFSCLC8(a) - modifies SYS_STACKHEAD by a and stores new value back in csci, if a > 128 then this is to be substracted
; IN:    a - value to increase
;        a - 0x00 - add
;            0x80 - sub
; OUT:csci - value of SYS_STACKHEAD with offset
;     dsdi - address of SYS_STACKHEAD
;        a - rubbish
stackoffsclc8: psh a
               psh a
               .mv dsdi, :{0}
               cal :peek16
               pop a
               and 0x80
               jmr nz, :stoffcl8_sub
               mov ds, 0x00
               pop di
               cal :add16
               xor a
               jmr z, :stoffcl8_end
stoffcl8_sub:  pop a
               and 0x7f
               mov di, a
               mov ds, 0x00
               cal :sub16  
stoffcl8_end:  .mv dsdi, :{0}
               ret
;=============
; STACKHEADROLL(csci, a) - modifies SYS_STACKHEAD by csci and saves new value
; IN: csci - value to increase
;        a - 0x00 - add
;            0x01 - sub
; OUT:csci - value of SYS_STACKHEAD
;     dsdi - address of SYS_STACKHEAD
;        a - rubbish
stackheadroll: cal :stackoffscalc
               cal :poke16
               .mv dsdi, :{0}
               ret
;=============
; STACKHEADRLL8(a) - modifies SYS_STACKHEAD by csci and saves new value
; IN:    a - value to increase
;        a - 0x00 - add
;            0x80 - sub
; OUT:csci - value of SYS_STACKHEAD
;     dsdi - address of SYS_STACKHEAD
;        a - rubbish
stackheadrll8: psh cs
               psh ci
               cal :stackoffsclc8
               cal :poke16
               .mv dsdi, :{0}
               pop ci
               pop cs
               ret
;=============
; STACKVARGET8(dsdi, a) - loads value of the variable of given offset dsdi from SYS_STACKHEAD to csci
; IN: dsdi - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x01 - sub
; OUT:ci - value of variable
;     cs - set to 0
;     dsdi - address of SYS_STACKHEAD
;        a - rubbish
stackvarget8:  mov cs, ds
               mov ci, di
               cal :stackoffscalc   
               mov a, #csci
               mov cs, 0x00
               mov ci, a
               ret
;=============
; STACKVARGET16(dsdi, a) - loads value of the variable of given offset dsdi from SYS_STACKHEAD to csci
; IN: dsdi - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x01 - sub
; OUT:csci - value of variable
;     dsdi - address of variable + 1
;        a - rubbish
stackvarget16: mov cs, ds
               mov ci, di
               cal :stackoffscalc
               mov ds, cs
               mov di, ci   
               cal :peek16
               ret
;=============
; STACKVARSET8(ci,dsdi, a) - loads value of the variable of given offset from SYS_STACKHEAD to csci
; IN: ci - value
;     dsdi - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x01 - sub
; OUT:csci - value of variable
;     dsdi - address of SYS_STACKHEAD
;        a - ci
stackvarset8:  psh ci
               mov cs, ds
               mov ci, di
               cal :stackoffscalc   
               pop a
               mov #csci, a
               ret
;=============
; STACKVARSET16(csci,dsdi, a) - loads value of the variable of given offset from SYS_STACKHEAD to csci
; IN: csci - value
;     dsdi - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x01 - sub
; OUT:csci - value
;     dsdi - address of variable + 1
;        a - ci
stackvarset16: psh cs
               psh ci
               mov cs, ds
               mov ci, di
               cal :stackoffscalc   
               mov ds, cs
               mov di, ci
               pop ci
               pop cs
               cal :poke16
               ret
;=============
; STACKVAR8GT8(a) - loads value of the variable of given offset a from SYS_STACKHEAD to csci
; IN:    a - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x80 - sub
; OUT:  ci - value of variable
;       cs - set to 0
;     dsdi - address of SYS_STACKHEAD
;        a - same as ci
stackvar8gt8:  cal :stackoffsclc8   
               mov a, #csci
               mov cs, 0x00
               mov ci, a
               ret
;=============
; STACKVAR8GT16(a) - loads value of the variable of given offset a from SYS_STACKHEAD to csci
; IN:    a - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x80 - sub
; OUT:csci - value of variable
;     dsdi - address of variable + 1
;        a - rubbish
stackvar8gt16: cal :stackoffsclc8
               mov ds, cs
               mov di, ci   
               cal :peek16
               ret
;=============
; STACKVAR8ST8(ci, a) - loads value of the variable of given offset from SYS_STACKHEAD to csci
; IN: ci - value
;        a - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x80 - sub
; OUT:  ci - value of variable
;     dsdi - address of SYS_STACKHEAD
;        a - ci
stackvar8st8:  psh ci
               cal :stackoffsclc8   
               pop a
               mov #csci, a
               ret
;=============
; STACKVAR8ST16(csci,a) - loads value of the variable of given offset from SYS_STACKHEAD to csci
; IN: csci - value
;        a - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x80 - sub
; OUT:csci - value
;     dsdi - address of variable + 1
;        a - rubbish
stackvar8st16: psh cs
               psh ci
               cal :stackoffsclc8   
               mov ds, cs
               mov di, ci
               pop ci
               pop cs
               cal :poke16
               ret
;=============
; MSEEK(csci) - finds address of first free block of given size
; IN: csci - wanted size of the block
; OUT:csci - address after which free memory begins
;     dsdi - address of the block after which is enough free memory
mseek:      .mv dsdi, :sys_seektmp
            cal :poke16
            .mv dsdi, :{1}
            cal :peek16
            mov ds, cs
            mov di, ci
mseek_loop: psh ds
            psh di
            cal :peek16
            psh cs
            psh ci
            cal :inc16
            cal :peek16
            pop f
            pop a
            psh cs
            psh ci
            psh a
            psh f
            cal :inc16           
            mov a, ci
            or cs
            jmr z, :mseek_end
            cal :sub16
            pop di
            pop ds
            cal :sub16
            psh cs
            psh ci
            .mv dsdi, :sys_seektmp
            cal :peek16
            mov ds, cs
            mov di, ci
            pop ci
            pop cs
            cal :gteq16
            jmr nz, :mseek_ret
            pop di
            pop ds
            pop a
            pop a
            xor a
            jmr z, :mseek_loop
mseek_end:  pop a
            pop a
            pop a
            pop a
            pop a
            pop a
            mov cs, ds
            mov ci, di            
            ret
mseek_ret:  pop di
            pop ds
            pop ci
            pop cs
            ret
;=============
; MFILL(csci,dsdi, a) - fills memory starting from dsdi for csci bytes of value a
; IN: csci - length
;     dsdi - address of memory
;        a - value to fill
mfill:      psh a
mfill_loop: mov a, cs
            or ci
            jmr z, :mfill_ret
            pop a
            psh a
            mov #dsdi, a
            cal :inc16
            psh ds
            psh di
            mov ds, cs
            mov di, ci
            cal :dec16
            mov cs, ds
            mov ci, di
            pop di
            pop ds
            xor a
            jmr z, :mfill_loop
mfill_ret:  pop a
            ret
; OUT:csci - address after which free memory begins
;     dsdi - address of the block after which is enough free memory
;=============
;SYS DATA
            .def var_promptbuf, 0x0bcf
            .def var_user_mem, 0x0bcb
sys_div16tmp: .db 0x00, 0x00
sys_seektmp: .db 0x00, 0x00 
{1}:  .db 0x{2:02x}, 0x{3:02x}
{0}: nop
"""