cmake_minimum_required(VERSION 3.22)
project(koine LANGUAGES C CXX)

if(MSVC)
    add_compile_options(/utf-8 /Zc:__cplusplus /permissive-)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND CMAKE_CXX_COMPILER_VERSION VERSION_LESS 12)
    message(FATAL_ERROR "Koine requires GCC 12+ because of GCC bug 66139 (exception cleanup). Use GCC 15; select CC=gcc-15 CXX=g++-15 in a fresh build directory.")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
include(FetchContent)
include(CTest)
if(CMAKE_VERSION VERSION_GREATER_EQUAL 4.0)
    set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
endif()
find_package(Threads REQUIRED)

FetchContent_Declare(cpp_peglib
    URL https://github.com/yhirose/cpp-peglib/archive/94a76a05dc90a344fe4f6ab37f5410cab4881704.tar.gz)
FetchContent_Declare(json
    URL https://github.com/nlohmann/json/archive/refs/tags/v3.11.3.tar.gz)
FetchContent_Declare(rapidyaml
    URL https://github.com/biojppm/rapidyaml/releases/download/v0.16.0/rapidyaml.v0.16.0.src.tgz
    URL_HASH SHA256=a0ce80a8f4211580c8703e57acb813a28ca6ec80908f6eb926be94be8e98d39d)
FetchContent_Declare(pcre2
    URL https://github.com/PCRE2Project/pcre2/releases/download/pcre2-10.39/pcre2-10.39.tar.gz
    URL_HASH SHA256=0781bd2536ef5279b1943471fdcdbd9961a2845e1d2c9ad849b9bd98ba1a9bd4)

set(BUILD_SHARED_LIBS OFF)
set(BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(PEGLIB_BUILD_BENCHMARK OFF CACHE BOOL "" FORCE)
set(JSON_BuildTests OFF CACHE BOOL "" FORCE)
set(JSON_Install OFF CACHE BOOL "" FORCE)
set(JSON_MultipleHeaders OFF CACHE BOOL "" FORCE)
set(RYML_DEFAULT_CALLBACK_USES_EXCEPTIONS ON CACHE BOOL "" FORCE)
set(RYML_WITH_TAB_TOKENS ON CACHE BOOL "" FORCE)
set(RYML_INSTALL OFF CACHE BOOL "" FORCE)
set(PCRE2_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(PCRE2_BUILD_PCRE2GREP OFF CACHE BOOL "" FORCE)
set(PCRE2_STATIC_PIC ON CACHE BOOL "" FORCE)
set(PCRE2_SHOW_REPORT OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(cpp_peglib json rapidyaml pcre2)

add_library(koine SHARED src/koine.cpp src/grammar.cpp src/yaml.cpp src/transpiler.cpp)
target_compile_definitions(koine PRIVATE KOINE_BUILD PCRE2_CODE_UNIT_WIDTH=8
    $<$<PLATFORM_ID:Windows>:PCRE2_STATIC>)
target_include_directories(koine PUBLIC include PRIVATE
    ${pcre2_BINARY_DIR})
target_link_libraries(koine PRIVATE peglib nlohmann_json::nlohmann_json
    ryml::ryml pcre2-8-static Threads::Threads)
set_target_properties(koine PROPERTIES
    C_VISIBILITY_PRESET hidden CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON
    LIBRARY_OUTPUT_DIRECTORY "$<1:${CMAKE_BINARY_DIR}/python/koine>"
    RUNTIME_OUTPUT_DIRECTORY "$<1:${CMAKE_BINARY_DIR}/python/koine>")
if(UNIX AND NOT APPLE)
    target_link_options(koine PRIVATE "LINKER:--exclude-libs,ALL")
endif()
if(WIN32)
    set_target_properties(koine PROPERTIES PREFIX "")
elseif(APPLE)
    set_target_properties(koine PROPERTIES INSTALL_NAME_DIR "@rpath")
endif()

configure_file(python/koine/__init__.py python/koine/__init__.py COPYONLY)
configure_file(python/koine/parser.py python/koine/parser.py COPYONLY)

foreach(component IN ITEMS python nim)
    install(TARGETS koine
        LIBRARY DESTINATION koine COMPONENT ${component}
        RUNTIME DESTINATION koine COMPONENT ${component}
        ARCHIVE DESTINATION koine COMPONENT ${component})
    install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/../LICENSE DESTINATION koine/licenses
        RENAME koine.txt COMPONENT ${component})
    install(FILES ${cpp_peglib_SOURCE_DIR}/LICENSE DESTINATION koine/licenses
        RENAME cpp-peglib.txt COMPONENT ${component})
    install(FILES ${json_SOURCE_DIR}/LICENSE.MIT DESTINATION koine/licenses
        RENAME nlohmann-json.txt COMPONENT ${component})
    install(FILES ${rapidyaml_SOURCE_DIR}/LICENSE.txt DESTINATION koine/licenses
        RENAME rapidyaml-c4core.txt COMPONENT ${component})
    install(FILES ${pcre2_SOURCE_DIR}/LICENCE DESTINATION koine/licenses
        RENAME pcre2.txt COMPONENT ${component})
    install(FILES licenses/fast_float.txt DESTINATION koine/licenses COMPONENT ${component})
endforeach()
install(FILES include/koine.h DESTINATION koine COMPONENT nim)

if(BUILD_TESTING)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_executable(koine_document_test tests/document.cpp src/yaml.cpp)
    target_include_directories(koine_document_test PRIVATE src ${json_SOURCE_DIR}/single_include)
    target_link_libraries(koine_document_test PRIVATE ryml::ryml)
    add_executable(koine_c_test tests/test_c_api.c)
    target_link_libraries(koine_c_test PRIVATE koine)
    add_test(NAME c_api COMMAND koine_c_test ${CMAKE_CURRENT_SOURCE_DIR}/../tests/calculator_parser.yaml)
    set_tests_properties(c_api PROPERTIES ENVIRONMENT_MODIFICATION "PATH=path_list_prepend:$<TARGET_FILE_DIR:koine>")
    add_executable(koine_lexer_c_test tests/test_lexer_c.c)
    target_link_libraries(koine_lexer_c_test PRIVATE koine)
    add_test(NAME lexer_c_api COMMAND koine_lexer_c_test)
    set_tests_properties(lexer_c_api PROPERTIES ENVIRONMENT_MODIFICATION "PATH=path_list_prepend:$<TARGET_FILE_DIR:koine>")
    add_executable(koine_transpiler_c_test tests/test_transpiler_c.c)
    target_link_libraries(koine_transpiler_c_test PRIVATE koine)
    add_test(NAME transpiler_c_api COMMAND koine_transpiler_c_test ${CMAKE_CURRENT_SOURCE_DIR}/tests/math_to_slip.yaml)
    set_tests_properties(transpiler_c_api PROPERTIES ENVIRONMENT_MODIFICATION "PATH=path_list_prepend:$<TARGET_FILE_DIR:koine>")
    add_test(NAME versions COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/check_versions.py)
    add_test(NAME python_api COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_native.py)
    set_tests_properties(python_api PROPERTIES ENVIRONMENT "PYTHONPATH=${CMAKE_BINARY_DIR}/python")
    add_test(NAME lexer_python COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_lexer.py)
    set_tests_properties(lexer_python PROPERTIES ENVIRONMENT "PYTHONPATH=${CMAKE_BINARY_DIR}/python")
    add_test(NAME transpiler_python COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_transpiler.py)
    set_tests_properties(transpiler_python PROPERTIES ENVIRONMENT "PYTHONPATH=${CMAKE_BINARY_DIR}/python")
    add_test(NAME parser_conformance COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/conformance.py)
    set_tests_properties(parser_conformance PROPERTIES ENVIRONMENT "PYTHONPATH=${CMAKE_BINARY_DIR}/python")
    add_test(NAME raw_asts COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/compare_asts.py)
    set_tests_properties(raw_asts PROPERTIES ENVIRONMENT "PYTHONPATH=${CMAKE_BINARY_DIR}/python")

    file(GLOB KOINE_GRAMMARS "${CMAKE_CURRENT_SOURCE_DIR}/../tests/*.yaml")
    add_test(NAME yaml_documents COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/tests/compare_documents.py $<TARGET_FILE:koine_document_test> ${KOINE_GRAMMARS})
    add_test(NAME regex_koine COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/tests/compare_regex.py ${KOINE_GRAMMARS})
    set_tests_properties(regex_koine PROPERTIES ENVIRONMENT "PYTHONPATH=${CMAKE_BINARY_DIR}/python")
endif()
