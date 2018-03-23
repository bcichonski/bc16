I allways wanted to build 8bit computer, as i am to lazy to work with hardware, this is the closest thing to that.

## architecture notes
microprocessor: bc8181
64kb address space
8 in and 8 out ports
no interrupts

### memory
memory: 16kb
4kb rom + 12kb ram with option to extend in future

### peripherals:
- terminal keyboard uses ports 0x0 and 0x8
- terminal printer uses ports 0x1 and 0x9
- cassette recorder uses ports 0x2 and 0xA
### the bc8181 microprocessor
#### registers:
```
0xF 0xE PC - 16bit
0xD SS - address of STACK segment
0xC SI - 8 bit stack index goes down from memory top

0xB F - 8bit processor flags
 0x0 - ZERO
 0x1 - CARRY
 0x2 - NEGATIVE
 0x3 - OVERFLOW
0x1 A - 8bit accumulator
0x4 CI - 8bit register addressing C segment
0x5 DI - 8bit register addressing D segment
0x8 CS - 8bit register storing address of C segment
0x9 DS - 8bit register storing address of D segment
```
#### instuctions
```
instructions are 1 or 2 bytes long:
B0(HL)B1(HL)
bc8181 instruction set B0H:
0x0 - NOP               ;
0x1 - MOV rno,imm        ; r=imm
0x2 - MOV rno1,rno2      ; r1 = r2
0x3 - MOV rno1,(rno2)    ; r1 = mem(r2) , r2 can be CI or DI
0x4 - MOV (rno1), rno2   ; mem(r1) = r2
0x5 - CLC A
  0x1 - add imm          ; A += imm
  0x9 - add rno          ; A += r
  0x2 - sub imm
  0xA - sub rno
  0x3 - and imm
  0xB - and rno
  0x4 - or imm
  0xC - or imm
  0x5 - xor imm
  0xD - xor rno
  0x6 - shl imm
  0x7 - shr imm
  0x8 - not A
  0xE - not_used
  0xF - not_used
0x6 - JMP t,(rno1,rno2)
  0x0 - if ZERO
  0x1 - if NOT ZERO
  0x2 - if CARRY
  0x3 - if NOT CARRY
  0x4 - if NEGATIVE
  0x5 - if NOT NEGATIVE
  0x6 - if OVERFLOW
  0x7 - if NOT OVERFLOW
  0x8-0xF is special mode where addres is CS:imm (its kind of short absolute jump)
0x7 - JMR t,imm7
  t like JMP, imm7 is 8bit signed value
  when t 0x8-0xF is special mode where rno is treated like imm7
0x8 - PSH rno
0x9 - POP rno
0xA - CAL (rno1,rno2)
0xB - RET
0xC - IN
 0x1 - rno, imm
 0x2 - rno1, rno2
0xD - OUT imm,rno
 0x1 - imm, rno1
 0x2 - rno1, rno2
0xE - not_used
0xF - HLT
```
