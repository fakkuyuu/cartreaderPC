// SPDX-License-Identifier: GPL-3.0-or-later
const fs=require('fs'),{execFileSync}=require('child_process');
const {CPU,avrInstruction}=require('avr8js');
const bytes=fs.readFileSync(process.argv[2]||'test.bin');
const flash=new Uint16Array(16384);for(let i=0;i<bytes.length;i+=2)flash[i/2]=bytes[i]|((bytes[i+1]||0)<<8);
const cpu=new CPU(flash,8192);
const nm=execFileSync(process.env.AVR_NM || 'avr-nm',[process.argv[3]||'test.elf'],{encoding:'utf8'});
function address(name){return parseInt(nm.match(new RegExp('([0-9a-f]+) [A-Za-z] '+name+'(?:\\r?\\n|$)'))[1],16)-0x800000;}
const result=address('test_result'),failed=address('failed_at'),count=address('test_count');
const word=a=>cpu.data[a]|cpu.data[a+1]<<8;
for(let n=0;n<20000000;n++){avrInstruction(cpu);cpu.tick();if(word(result)===0x600d || word(result)===0xdead){const ok=word(result)===0x600d;console.log(ok?'PASS':'FAIL','checks='+word(count),'failed_at='+word(failed));process.exit(ok?0:1);}}
throw Error('test timed out pc='+cpu.pc);
