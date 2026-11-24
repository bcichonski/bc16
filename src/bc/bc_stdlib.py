"""Assembly runtime (stdlib) of the compiler, split into named fragments.

Each fragment is one routine (the boundaries are the former `;=============` sections of the single
template, kept in template order) with its text and a DECLARED list of the fragments it depends on.
The compiler emits only the fragments referenced by the kept code plus the closure of their declared
dependencies (Context.add_stdlib); a unit test checks that the declaration equals the labels the
text really references.

Each fragment is meant to become one `.sect` of runtime.basm in #116 (then linked by blink, #126).

Text is a format template: {0} = sys_stackhead, {1} = sys_heaphead (names). Always emitted:
the banner, the head, sys_heaphead, sys_stackhead (last byte of the image) and sys_codeend.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Fragment:
    name: str
    text: str
    deps: tuple = ()


runtime_banner = """
;>>>>>>>>>>COMPILER ASM STDLIB for BCOS v1.2 on BC64 v1.0<<<<<<<<<<<<<
"""

# 8 bytes, no label, purpose undocumented - kept as the head of the runtime (assumption A-1 of #16)
runtime_head = """            mov a, 0xff
            mov a, 0xff
            mov a, 0xff
            mov a, 0xff
"""

runtime_fragments = [
    Fragment('os_metacall', """;=============
; OS_METACALL(a) - calls given bcos subroutine indirectly
;           - other registers as required
; OUT:      - as returned
            .def os_metacall, 0x0008
"""),
    Fragment('fatal', """;=============
; FATAL(a) - prints error message and stops
; IN:   a - error code
;   stack - as error address
; OUT:  KILL, messed stack
fatal:          psh ci
                mov ci, 0x14
                psh ci
                pop f
                pop ci
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('printhex4', """;=============
; PRINTHEX4(a) - prints hex number from 0 to f
; IN:    a - number to print
; OUT:   a - unchanged      10 -> 0 -> 41
;       cs - set to 1
printhex4:      psh ci
                mov ci, 0x03
                psh ci
                pop f
                pop ci
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('printhex8', """;=============
; PRINTHEX8(a) - prints hex number 
; IN:    a - number to print
; OUT:   a - set to lower half
;     csci - unchanged
;     dsdi - unchanged
printhex8:      psh ci
                mov ci, 0x04
                psh ci
                pop f
                pop ci
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('printhex16', """;=============
; PRINTHEX16(csci) - prints hex number 4 digits
; IN:    csci - hex number 4 digits
; OUT:   csci - unchanged
;           a - ci
printhex16:     mov a, 0x05
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('poke16', """;=============
; POKE16(#dsdi, csci) - stores csci value under #dsdi address (2 bytes)
; IN:   dsdi - address to store
;       csci - value to store
; OUT:  dsdi - address to store + 1
;       csci - unchanged
;       a    - rubbish
poke16:        mov #dsdi, cs
               inc dsdi
               mov #dsdi, ci
poke16_ok:     ret
"""),
    Fragment('peek16', """;=============
; PEEK16(#dsdi) - returns value under dsdi address (2 bytes)
; IN:   dsdi - address to read
; OUT:  dsdi - address to read + 1
;       csci - value
;       a    - rubbish
peek16:        mov cs, #dsdi
               inc dsdi
               mov ci, #dsdi
peek16_ok:     ret
"""),
    Fragment('readstr', """;=============
; READSTR(#dsdi, ci) - reads characters to the buffer
; IN:   dsdi - buffer address for chars
;         ci - length of the buffer (since last char has to be 0x00 we can enter one less)
; OUT:  dsdi - preserved
;         ci - preserved
;         cs - how many chars can we could still add
readstr:        mov a, 0x0d
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('nextword', """;=============
; NEXTWORD(dsdi) - moves to the end of current word
; IN:     dsdi - char buffer address
; OUT:    dsdi - address of the next word or end of buffer
;            a - >0 if next word exist
nextword:       mov a, 0x12
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('nextval8', """;=============
; NEXTVAL8(dsdi) - moves until expected value
; IN:     dsdi - char buffer address
;           ci - expected 8bit value
;           cs - max length to check
; OUT:    dsdi - address of the next byte or end of buffer
;           cs - how much was left to end of buffer
;           ci - unchanged
;            a - >0 if value was found
nextval8:       mov a, 0x13
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('upchar', """;=============
; #11: UPCHAR(a) - if a is an a-z char returns A-Z
; IN:     a - char code
; OUT:    a - char code A-Z or same
;         ci - old a val
upchar:         psh a
                mov a, 0x11
                psh a
                pop f
                pop a
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('str_cpy', """;=============
; STR_CPY(csci,dsdi)  - copy string from dsdi to csci
; IN: dsdi - source  
;     csci - desc
; OUT: dsdi = source + length + 1
str_cpy:        mov a, 0x17
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('str_len8', """;=============
; STR_LEN8(dsdi)  - length of the string ending with 0x00
; IN: dsdi - source  
;     cs   - max length
; OUT: dsdi - preserved, cs = rubbish, ci = actual length
str_len8:       mov a, 0x18
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('parsehex4', """;=============
; PARSEHEX4(#dsdi) - parses single char to hex number chars 0-9 and a-z and A-Z are supported
; IN:   dsdi - buffer address for char-hex
; OUT:     a - 0 if ok, 0xff if parse error
;         ci - hexval of a char
parsehex4:      mov a, 0x0e
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('parsehex8', """;=============
; PARSEHEX8(#dsdi) - parses two char to hex number
; IN:   dsdi - buffer address for char
; OUT:    a - success = 0 or >0 error
;        ci - hex value for byte
;      dsdi - moved + 2 if ok
parsehex8:      mov a, 0x0f
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('parsehex16', """;=============
; PARSEHEX16(#dsdi) - parses four char to hex number
; IN:   dsdi - buffer address for char
; OUT:  csci - hex value for value
;          a - success = 0 or error code
;       dsdi - moved + 4 if ok
parsehex16:     mov a, 0x10
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('print_newline', """;=============
; PRINT_NEWLINE - prints new line
; IN:
; OUT:   a - rubbish
print_newline:  mov a, 0x00
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('printstr', """;=============
; PRINTSTR(*dsdi) - sends chars to printer
; IN: dsdi - address of 0-ended char table
; OUT:   a - set to 0x00
;       ci - set to 0x01
;     dsdi - set to end of char table
printstr:       mov a, 0x02
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('gt16', """;=============
; GT16(csci,dsdi) - compares csci with dsdi            
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  a - 1 if csci > dsdi
;       a - 0 otherwise
gt16:           mov a, 0x21
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('gteq16', """;=============
; GTEQ16(csci,dsdi) - compares csci with dsdi            
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  a - 1 if csci >= dsdi
;       a - 0 otherwise
gteq16:         mov a, 0x22
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('eq16', """;=============
; EQ16(csci,dsdi) - compares csci with dsdi            
; IN:   csci - argument 1
;       dsdi - argument 2
; OUT:  a - 1 if csci == dsdi
;       a - 0 otherwise
eq16:           mov a, 0x23
                psh a
                pop f
                cal :os_metacall
                ret
""", ('os_metacall',)),
    Fragment('stackoffscalc', """;=============
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
               clr :peek16
               pop di
               pop ds
               pop a
               and a
               jmr nz, :stoffclc_sub
               add csci, dsdi
               xor a
               jmr z, :stoffclc_end
stoffclc_sub:  sub csci, dsdi  
stoffclc_end:  .mv dsdi, :{0}
               ret
""", ('peek16',)),
    Fragment('stackoffsclc8', """;=============
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
               clr :peek16
               pop a
               and 0x80
               jmr nz, :stoffcl8_sub
               mov ds, 0x00
               pop di
               add csci, dsdi
               xor a
               jmr z, :stoffcl8_end
stoffcl8_sub:  pop a
               and 0x7f
               mov di, a
               mov ds, 0x00
               sub csci, dsdi 
stoffcl8_end:  .mv dsdi, :{0}
               ret
""", ('peek16',)),
    Fragment('stackheadroll', """;=============
; STACKHEADROLL(csci, a) - modifies SYS_STACKHEAD by csci and saves new value
; IN: csci - value to increase
;        a - 0x00 - add
;            0x01 - sub
; OUT:csci - value of SYS_STACKHEAD
;     dsdi - address of SYS_STACKHEAD
;        a - rubbish
stackheadroll: clr :stackoffscalc
               clr :poke16
               .mv dsdi, :{0}
               ret
""", ('poke16', 'stackoffscalc')),
    Fragment('stackheadrll8', """;=============
; STACKHEADRLL8(a) - modifies SYS_STACKHEAD by csci and saves new value
; IN:    a - value to increase
;        a - 0x00 - add
;            0x80 - sub
; OUT:csci - value of SYS_STACKHEAD
;     dsdi - address of SYS_STACKHEAD
;        a - rubbish
stackheadrll8: psh cs
               psh ci
               clr :stackoffsclc8
               clr :poke16
               .mv dsdi, :{0}
               pop ci
               pop cs
               ret
""", ('poke16', 'stackoffsclc8')),
    Fragment('stackvarget8', """;=============
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
               clr :stackoffscalc   
               mov a, #csci
               mov cs, 0x00
               mov ci, a
               ret
""", ('stackoffscalc',)),
    Fragment('stackvarget16', """;=============
; STACKVARGET16(dsdi, a) - loads value of the variable of given offset dsdi from SYS_STACKHEAD to csci
; IN: dsdi - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x01 - sub
; OUT:csci - value of variable
;     dsdi - address of variable + 1
;        a - rubbish
stackvarget16: mov cs, ds
               mov ci, di
               clr :stackoffscalc
               mov ds, cs
               mov di, ci   
               clr :peek16
               ret
""", ('peek16', 'stackoffscalc')),
    Fragment('stackvarset8', """;=============
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
               clr :stackoffscalc   
               pop a
               mov #csci, a
               ret
""", ('stackoffscalc',)),
    Fragment('stackvarset16', """;=============
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
               clr :stackoffscalc   
               mov ds, cs
               mov di, ci
               pop ci
               pop cs
               clr :poke16
               ret
""", ('poke16', 'stackoffscalc')),
    Fragment('stackvar8gt8', """;=============
; STACKVAR8GT8(a) - loads value of the variable of given offset a from SYS_STACKHEAD to csci
; IN:    a - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x80 - sub
; OUT:  ci - value of variable
;       cs - set to 0
;     dsdi - address of SYS_STACKHEAD
;        a - same as ci
stackvar8gt8:  clr :stackoffsclc8   
               mov a, #csci
               mov cs, 0x00
               mov ci, a
               ret
""", ('stackoffsclc8',)),
    Fragment('stackvar8gt16', """;=============
; STACKVAR8GT16(a) - loads value of the variable of given offset a from SYS_STACKHEAD to csci
; IN:    a - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x80 - sub
; OUT:csci - value of variable
;     dsdi - address of variable + 1
;        a - rubbish
stackvar8gt16: clr :stackoffsclc8
               mov ds, cs
               mov di, ci   
               clr :peek16
               ret
""", ('peek16', 'stackoffsclc8')),
    Fragment('stackvar8st8', """;=============
; STACKVAR8ST8(ci, a) - loads value of the variable of given offset from SYS_STACKHEAD to csci
; IN: ci - value
;        a - offset from SYS_STACKHEAD
;        a - 0x00 - add
;            0x80 - sub
; OUT:  ci - value of variable
;     dsdi - address of SYS_STACKHEAD
;        a - ci
stackvar8st8:  psh ci
               clr :stackoffsclc8   
               pop a
               mov #csci, a
               ret
""", ('stackoffsclc8',)),
    Fragment('stackvar8st16', """;=============
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
               clr :stackoffsclc8   
               mov ds, cs
               mov di, ci
               pop ci
               pop cs
               clr :poke16
               ret
""", ('poke16', 'stackoffsclc8')),
    Fragment('mseek', """;=============
; MSEEK(csci) - finds address of first free block of given size
; IN: csci - wanted size of the block
; OUT:csci - address after which free memory begins
;     dsdi - address of the block after which is enough free memory
mseek:      .mv dsdi, :sys_seektmp
            clr :poke16
            .mv dsdi, :{1}
            clr :peek16
            mov ds, cs
            mov di, ci
mseek_loop: psh ds
            psh di
            clr :peek16
            psh cs
            psh ci
            inc dsdi
            clr :peek16
            pop f
            pop a
            psh cs
            psh ci
            psh a
            psh f
            inc dsdi
            mov a, ci
            or cs
            jmr z, :mseek_end
            sub csci, dsdi
            pop di
            pop ds
            sub csci, dsdi
            psh cs
            psh ci
            .mv dsdi, :sys_seektmp
            clr :peek16
            mov ds, cs
            mov di, ci
            pop ci
            pop cs
            clr :gteq16
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
""", ('poke16', 'peek16', 'gteq16', 'sys_seektmp')),
    Fragment('mfill', """;=============
; MFILL(csci,dsdi, a) - fills memory starting from dsdi for csci bytes of value a
; IN: csci - length
;     dsdi - address of memory
;        a - value to fill
; OUT:csci - address after which free memory begins
;     dsdi - address of the block after which is enough free memory
mfill:      psh a
            mov a, 0x31
            psh a
            pop f
            pop a
            cal :os_metacall
            ret
""", ('os_metacall',)),
    Fragment('mem_cpy', """;=============
; MEM_CPY(csci,dsdi, af)  - copy block of memory from csci to dsdi for at most af bytes
; IN: dsdi - source  
;     csci - desc
;       af - length
; OUT: dsdi = destroyed
;      csci = desc + length + 1
mem_cpy:    psh cs
            psh ci
            psh a
            psh f
            pop ci
            pop cs
            mov a, 0x08
            psh a
            pop f
            cal :os_metacall
            mov a, 0x32
            psh a
            pop f
            pop ci
            pop cs
            cal :os_metacall
            ret
""", ('os_metacall',)),
    Fragment('strncpy', """;=============
; strncpy(csci,dsdi, a)  - copy string from dsdi to csci for at most a bytes, or end of string
; IN: dsdi - source  
;     csci - desc
;        a - length
; OUT: dsdi = desc + length + 1
;      csci = source + length
strncpy:    psh a
            mov a, 0x33
            psh a
            pop f
            pop a
            cal :os_metacall
            ret
""", ('os_metacall',)),
    Fragment('sys_stdprntf', """sys_stdprntf:.db 0x00, 0x00
"""),
    Fragment('sys_seektmp', """sys_seektmp: .db 0x00, 0x00
"""),
]

# sys_heaphead data ({2}, {3} = heap segment address hi, lo), then sys_stackhead as the last byte
runtime_tail = """{1}:  .db 0x{2:02x}, 0x{3:02x}
{0}: nop
"""
