# Issue 104: code size before and after removing the label nop

| program | before (bytes) | after (bytes) | change |
| :--- | ---: | ---: | ---: |
| bdos/bdos | 17623 | 17359 | -264 |
| bdos/calc | 6418 | 6307 | -111 |
| bdos/cat | 7908 | 7767 | -141 |
| bdos/cha | 7159 | 7029 | -130 |
| bdos/cp | 7214 | 7095 | -119 |
| bdos/debug | 586 | 585 | -1 |
| bdos/fddtest | 3519 | 3444 | -75 |
| bdos/format | 10466 | 10307 | -159 |
| bdos/helloworld | 1665 | 1628 | -37 |
| bdos/ls | 7441 | 7318 | -123 |
| bdos/rm | 8045 | 7915 | -130 |
| bdos/texted | 14359 | 14150 | -209 |
| bdos/theodore | 4843 | 4758 | -85 |
| code/declarations | 682 | 678 | -4 |
| code/functions | 600 | 598 | -2 |
| code/funrec | 645 | 642 | -3 |
| code/stdmemtest | 817 | 810 | -7 |
| code/strings | 680 | 675 | -5 |
| **total** | 100670 | 99065 | -1605 |

Measured with scripts/code_size.py from builds of 53e6ac3 (before) and this branch (after).
