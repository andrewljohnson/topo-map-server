import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const code=ts.transpileModule(fs.readFileSync(new URL('../../web/app/tileUrls.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText;
const {tileTemplateUrl}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
test('web tile templates preserve substitution tokens and dataset query values',()=>{
 const template=tileTemplateUrl('/tiles/{z}/{x}/{y}.pbf?datasetId=us-v7','http://localhost:3001');
 assert.equal(template,'http://localhost:3001/tiles/{z}/{x}/{y}.pbf?datasetId=us-v7');
 assert.equal(template.replace('{z}',3).replace('{x}',1).replace('{y}',3),'http://localhost:3001/tiles/3/1/3.pbf?datasetId=us-v7');
 assert.equal(tileTemplateUrl('https://tiles.example/tiles/{z}/{x}/{y}.pbf','http://localhost:3001'),'https://tiles.example/tiles/{z}/{x}/{y}.pbf');
});
