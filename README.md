I have always wanted to build 8bit computer, as i am to lazy to work with hardware, this is the closest thing to that.

# BC32
## roadmap
0. smaller peripherals
1. fdd
2. memory extension
3. bcos upgrade
4. bdos development
5. new binary file format
6. new assembler
7. new blang compiler

## architectural notes
### OS
bcos v1.1 
 - some procedures from b compiler stdlib incorporated
 - minor fixes
 - still tape-only suport with for .btap files
 - new code to recognize presence of floppy disk drive to boot their system

bdos v1
 - disk operation system
   - micromode (the os itself just knows how to load and run executables)
 - bfs file system
   - only files
   - but with some attributes

### CPU
microprocessor: bc8182 (very small fixes regarding f register)
64kb address space
16 in/out ports
no interrupts
one extension slot (basically allows a device to use memory directly)

## memory
memory: 32kb
~6kb rom + 26kb ram with option to extend in future

### peripherals
same as BC16 plus
- real time clock 0x3
- random generator 0x4
- floppy disk drive 0x8
  - port 0x8 used for instructions and communication:
    - 0xf0 - ping with response with version of the drive: returns READY | FDVER1
    - 0xf1 <imm16> - configure DMA - sets where drive can put read sector, always 128 bytes returns READY
    - 0xfa - set active drive A returns READY
    - 0xfb - set active drive B returns READY
    - 0xf2 <imm8:t> <imm8:s> - reads sector s from track t returns READY or CFGERROR or CMDERROR
    - 0xf3 <imm8:t> <imm8:s> - writes sector s from track t returns READY or CFGERROR or CMDERROR
    - 0xf4 - eject active drive
    - response codes:
      - READY: 0x10
      - FDVER1: 0x01
      - CFGERROR: 0xe1
      - CMDERROR: 0xe2

  - uses direct memory access to read entire sector
  - double drive for single side 3" floppy disks that has 64 tracks of 16 sectors of 128 bytes = 128 KB

# BC16
## architectural notes
### OS
bcos v1.0
tape-only suport with for .btap files

### CPU
microprocessor: bc8181 - bc8182
64kb address space
16 in/out ports
no interrupts

### memory
memory: 16kb
4kb rom + 12kb ram with option to extend in future

### the bc8182 microprocessor
same as bc8181 but with some small errors fixed
some extentions like 16bit arithmetic? or 8bit div/mod/mul


### peripherals:
- terminal keyboard uses io ports 0x0
- terminal printer uses io ports 0x1
- cassette recorder uses io ports 0x2
  ports 0x2 are used for manipulating recorder:
    valid commands to sent via 0x2 output port:
    0x80 - load tape - set this bit and question for the name of the tape file to read will appear; only one of 0x80/0x40 flag can be set
    0x40 - save tape - set this bit and question for the name of the tape file to save will appear; only one of 0x80/0x40 flag can be set
    0x20 - start/stop moving recorder engine, initiates/ends read/write sequence
    0x01 - reserved for writing or reading bit to/from the device    
    0x10 - ready flag - if device is ready for reading next command
    0x08 - error flag - ie when tape is full

  example session for writing to the tape:
  read 0x2 port

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
0x3 - MOV rno1,(rno2, rno3)    ; r1 = mem(r2) , r2 can be CI or DI
0x4 - MOV (rno1,rno2), rno3   ; mem(r1) = r2
0x5 - CLC A
  0x0 - add imm          ; A += imm
  0x8 - add rno          ; A += r
  0x1 - sub imm
  0x9 - sub rno
  0x2 - and imm
  0xA - and rno
  0x3 - or imm
  0xB - or rno
  0x4 - xor imm
  0xC - xor rno
  0x5 - shl imm
  0x6 - shr imm
  0x7 - not A - only 1 byte
  0xD - inc A - only 1 byte!
  0xE - dec A - only 1 byte!
  0xF - not used for future extensions
0x6 - JMP t,(rno1,rno2)
  0x0 - if ZERO
  0x4 - if NOT ZERO
  0x1 - if CARRY
  0x5 - if NOT CARRY
  0x2 - if NEGATIVE
  0x6 - if NOT NEGATIVE
  0x3 - if OVERFLOW
  0x7 - if NOT OVERFLOW
  0x8-0xF is special mode where addres is CS:imm (its kind of short absolute jump)
0x7 - JMR t,imm7
  t like JMP, imm7 is 8bit signed value
  when t 0x8-0xF is special mode where rno is treated like imm7
0x8 - PSH rno
0x9 - POP rno
0xA - CAL 
  0x0 (rno1,rno2)
  0x8 imm16
0xB - RET
0xC - IN
 0x0-0x7 - rno, #imm
 0x8-0xf - rno1, #rno2
0xD - OUT imm,rno
 0x0-0x7 - #rno1, imm
 0x8-0xf - #rno1, rno2
0xE - NOP not_used
0xF - KIL
```
### software
external assembler bc81asmc up to 1.1 (240317)
external compiler bc of b language for bc8181-bc8182 cpu v 1.0.0 (240317)
calc - basic calculator
texted - basic line editor
theodore - simple game

