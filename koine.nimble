version = "0.11.0"
author = "Chris Bates"
description = "Runtime grammars, native parsing and AST transpilation over Koine's C API"
license = "MIT"
srcDir = "nim"
installFiles = @["koine.nim"]
installDirs = @["koine"]
requires "nim >= 2.0.0"

before install:
  exec "cmake -S native -B build/nim -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release"
  exec "cmake --build build/nim --target koine --parallel 2 --config Release"
  exec "cmake --install build/nim --prefix nim --component nim --config Release"
