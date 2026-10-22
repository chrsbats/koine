## Timed ordinary API calls: C JSON emission plus Nim JsonNode conversion included.
import std/[json, monotimes, os, strutils, times]
import koine

let grammarPath = paramStr(1)
let source = readFile(paramStr(2))
let iterations = parseInt(paramStr(3))
let startRule = if paramCount() >= 4: paramStr(4) else: ""
let outputPath = if paramCount() >= 5: paramStr(5) else: ""
let begin = getMonoTime()
let parser = parserFromFile(grammarPath)
let transpiler = if outputPath.len > 0: transpilerFromFile(outputPath) else: nil
let prepared = (getMonoTime() - begin).inNanoseconds.float / 1e9
let first = parser.parse(source, startRule)
doAssert first["status"].getStr == "success"
let expectedText = if transpiler.isNil: "" else: transpiler.transpile(first["ast"])
let started = getMonoTime()
for i in 0..<iterations:
  let parsed = parser.parse(source, startRule)
  doAssert parsed["status"].getStr == "success"
  if not transpiler.isNil:
    discard transpiler.transpile(parsed["ast"])
let elapsed = (getMonoTime() - started).inNanoseconds.float / 1e9
var combinedElapsed = 0.0
if not transpiler.isNil:
  let combinedStarted = getMonoTime()
  for i in 0..<iterations:
    let combined = parser.parseTranspile(transpiler, source, startRule)
    doAssert combined["status"].getStr == "success"
    doAssert combined["text"].getStr == expectedText
  combinedElapsed = (getMonoTime() - combinedStarted).inNanoseconds.float / 1e9
let encoded = $first
let decodeStarted = getMonoTime()
for i in 0..<iterations:
  discard parseJson(encoded)
let decodeElapsed = (getMonoTime() - decodeStarted).inNanoseconds.float / 1e9
let report = %* {"prepare_seconds": prepared, "seconds_per_call": elapsed / iterations.float,
                "combined_seconds_per_call": combinedElapsed / iterations.float,
                "json_decode_seconds": decodeElapsed / iterations.float,
                "result": first, "text": expectedText}
echo $report
